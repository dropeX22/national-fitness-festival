"""
models.py
---------
Define las tablas de la base de datos usando SQLAlchemy (ORM).
Cada clase = una tabla. Cada atributo de la clase = una columna.
"""

import enum
import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey, Float, Enum, Text, UniqueConstraint
)
from sqlalchemy.orm import relationship
from app.database import Base


# ---------------------------------------------------------------------------
# ENUMS: valores fijos que puede tomar una columna (evitan strings sueltos)
# ---------------------------------------------------------------------------

class CategoriaEnum(str, enum.Enum):
    principiante = "Principiante"
    avanzado = "Avanzado"


class GeneroEnum(str, enum.Enum):
    masculino = "M"
    femenino = "F"


class EstadoEquipoEnum(str, enum.Enum):
    pendiente = "Pendiente"          # Creado, esperando pago
    pagado = "Pagado"                # Pago confirmado -> inscripción válida
    cancelado = "Cancelado"          # Cancelado por el admin


class EstadoPagoEnum(str, enum.Enum):
    pendiente = "Pendiente"
    confirmado = "Confirmado"
    rechazado = "Rechazado"


# ---------------------------------------------------------------------------
# TABLA: Evento
# ---------------------------------------------------------------------------

class Evento(Base):
    __tablename__ = "eventos"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(150), nullable=False, default="National Fitness Festival")
    fecha = Column(DateTime, nullable=False)
    descripcion = Column(Text, nullable=True)
    precio_inscripcion = Column(Float, nullable=False, default=200.0)  # precio por equipo
    # Solo debe haber UN evento con activo=True a la vez: es "el evento de
    # este año", al que se conectan las nuevas inscripciones. Los eventos
    # de años anteriores se quedan en la base de datos con activo=False,
    # como historial, pero ya no reciben inscripciones nuevas.
    activo = Column(Boolean, nullable=False, default=True)

    equipos = relationship("Equipo", back_populates="evento")


# ---------------------------------------------------------------------------
# TABLA: Equipo
# ---------------------------------------------------------------------------

class Equipo(Base):
    __tablename__ = "equipos"

    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(20), unique=True, index=True, nullable=False)  # Ej: NF-001
    nombre = Column(String(100), nullable=False, index=True)
    categoria = Column(Enum(CategoriaEnum), nullable=False, index=True)

    # El capitán es uno de los atletas del equipo. Usamos una FK que se
    # completa DESPUÉS de crear a los atletas (por eso nullable=True).
    capitan_id = Column(Integer, ForeignKey("atletas.id"), nullable=True)

    reglamento_aceptado = Column(Boolean, nullable=False, default=False)
    estado = Column(Enum(EstadoEquipoEnum), nullable=False, default=EstadoEquipoEnum.pendiente, index=True)

    evento_id = Column(Integer, ForeignKey("eventos.id"), nullable=False)
    fecha_creacion = Column(DateTime, default=datetime.datetime.utcnow)

    # Relaciones
    evento = relationship("Evento", back_populates="equipos")
    # foreign_keys explícito porque hay 2 FKs relacionadas con Atleta/Equipo (equipo_id y capitan_id)
    atletas = relationship(
        "Atleta", back_populates="equipo", foreign_keys="Atleta.equipo_id", cascade="all, delete-orphan"
    )
    capitan = relationship("Atleta", foreign_keys=[capitan_id], post_update=True)
    pagos = relationship("Pago", back_populates="equipo", cascade="all, delete-orphan")
    checkin = relationship("CheckIn", back_populates="equipo", uselist=False, cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# TABLA: Atleta
# ---------------------------------------------------------------------------

class Atleta(Base):
    __tablename__ = "atletas"
    # Antes la cédula era única en TODA la tabla, lo que impedía que un
    # mismo atleta volviera a inscribirse en un evento futuro. Ahora la
    # combinación (cedula, evento_id) es la que debe ser única: la misma
    # persona SÍ puede repetir cédula de un año a otro, pero NO puede
    # inscribirse dos veces dentro del mismo evento.
    __table_args__ = (
        UniqueConstraint("cedula", "evento_id", name="uq_cedula_por_evento"),
    )

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(150), nullable=False)
    cedula = Column(String(30), index=True, nullable=False)  # única junto con evento_id, no sola
    email = Column(String(150), nullable=False)
    telefono = Column(String(30), nullable=True)
    genero = Column(Enum(GeneroEnum), nullable=False)

    equipo_id = Column(Integer, ForeignKey("equipos.id"), nullable=False)
    # Guardamos evento_id también aquí (aunque ya se puede llegar a él vía
    # equipo.evento_id) porque así la base de datos puede aplicar la regla
    # de unicidad directamente, sin tener que consultar la tabla Equipo.
    evento_id = Column(Integer, ForeignKey("eventos.id"), nullable=False, index=True)

    equipo = relationship("Equipo", back_populates="atletas", foreign_keys=[equipo_id])


# ---------------------------------------------------------------------------
# TABLA: Pago
# ---------------------------------------------------------------------------

class Pago(Base):
    __tablename__ = "pagos"

    id = Column(Integer, primary_key=True, index=True)
    equipo_id = Column(Integer, ForeignKey("equipos.id"), nullable=False, index=True)
    monto = Column(Float, nullable=False)
    estado = Column(Enum(EstadoPagoEnum), nullable=False, default=EstadoPagoEnum.pendiente, index=True)
    fecha = Column(DateTime, default=datetime.datetime.utcnow)
    referencia_yappy = Column(String(100), unique=True, nullable=True, index=True)

    equipo = relationship("Equipo", back_populates="pagos")


# ---------------------------------------------------------------------------
# TABLA: CheckIn
# ---------------------------------------------------------------------------

class CheckIn(Base):
    __tablename__ = "checkins"

    id = Column(Integer, primary_key=True, index=True)
    equipo_id = Column(Integer, ForeignKey("equipos.id"), unique=True, nullable=False, index=True)
    fecha_hora = Column(DateTime, nullable=True)
    kit_entregado = Column(Boolean, default=False)
    responsable = Column(String(100), nullable=True)  # quién hizo el check-in (staff)

    equipo = relationship("Equipo", back_populates="checkin")
