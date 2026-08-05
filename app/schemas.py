"""
schemas.py
----------
Esquemas Pydantic: definen la "forma" de los datos que entran y salen de
la API (validación automática). No son tablas de BD, son solo estructuras
de datos para las peticiones HTTP.
"""

from pydantic import BaseModel, EmailStr, field_validator
from typing import List, Optional
from datetime import datetime
from app.models import CategoriaEnum, GeneroEnum, EstadoEquipoEnum, EstadoPagoEnum


# ---------------------------------------------------------------------------
# ATLETA
# ---------------------------------------------------------------------------

class AtletaCreate(BaseModel):
    nombre: str
    cedula: str
    email: EmailStr
    telefono: Optional[str] = None
    genero: GeneroEnum
    es_capitan: bool = False  # marcamos cuál de los 4 es el capitán


class AtletaOut(BaseModel):
    id: int
    nombre: str
    cedula: str
    email: str
    telefono: Optional[str] = None
    genero: GeneroEnum

    class Config:
        from_attributes = True  # permite convertir desde objetos SQLAlchemy


# ---------------------------------------------------------------------------
# EQUIPO
# ---------------------------------------------------------------------------

class EquipoCreate(BaseModel):
    nombre: str
    categoria: CategoriaEnum
    reglamento_aceptado: bool
    consentimiento_datos_aceptado: bool
    atletas: List[AtletaCreate]

    @field_validator("atletas")
    @classmethod
    def validar_equipo(cls, atletas: List[AtletaCreate]):
        # Regla de negocio: exactamente 4 integrantes (2H y 2M)
        if len(atletas) != 4:
            raise ValueError("El equipo debe tener exactamente 4 integrantes")

        hombres = [a for a in atletas if a.genero == GeneroEnum.masculino]
        mujeres = [a for a in atletas if a.genero == GeneroEnum.femenino]
        if len(hombres) != 2 or len(mujeres) != 2:
            raise ValueError("El equipo debe tener exactamente 2 hombres y 2 mujeres")

        capitanes = [a for a in atletas if a.es_capitan]
        if len(capitanes) != 1:
            raise ValueError("Debe haber exactamente un capitán marcado")

        cedulas = [a.cedula.strip() for a in atletas]
        if len(set(cedulas)) != len(cedulas):
            raise ValueError("No puede haber cédulas repetidas dentro del mismo equipo")

        return atletas

    @field_validator("reglamento_aceptado")
    @classmethod
    def validar_reglamento(cls, valor: bool):
        if not valor:
            raise ValueError("El capitán debe aceptar el reglamento para inscribir al equipo")
        return valor
    @field_validator("consentimiento_datos_aceptado")
    @classmethod
    def validar_consentimiento_datos(cls, valor: bool):
        if not valor:
            raise ValueError("Debes aceptar el tratamiento de tus datos personales para inscribirte")
        return valor


class EquipoOut(BaseModel):
    id: int
    codigo: str
    nombre: str
    categoria: CategoriaEnum
    estado: EstadoEquipoEnum
    reglamento_aceptado: bool
    fecha_creacion: datetime
    atletas: List[AtletaOut] = []

    class Config:
        from_attributes = True


class EquipoAdminOut(EquipoOut):
    """Versión extendida para el panel de admin (incluye info de pago)."""
    monto_pagado: Optional[float] = None
    capitan_nombre: Optional[str] = None
    capitan_email: Optional[str] = None


# ---------------------------------------------------------------------------
# PAGO
# ---------------------------------------------------------------------------

class PagoCreate(BaseModel):
    monto: float


class PagoOut(BaseModel):
    id: int
    equipo_id: int
    monto: float
    estado: EstadoPagoEnum
    fecha: datetime
    referencia_yappy: Optional[str] = None

    class Config:
        from_attributes = True


class WebhookYappyPayload(BaseModel):
    """
    Estructura esperada del webhook de Yappy. En producción, revisar la
    documentación real de 'Yappy Comercial' para los nombres exactos de
    los campos; aquí usamos nombres razonables y fáciles de adaptar.
    """
    referencia_yappy: str
    estado: str  # "confirmado" | "rechazado"
    monto: float


# ---------------------------------------------------------------------------
# CHECK-IN
# ---------------------------------------------------------------------------

class CheckInBuscar(BaseModel):
    termino: str  # nombre del equipo o código (NF-001)


class CheckInRegistrar(BaseModel):
    equipo_id: int
    responsable: str
    kit_entregado: bool = True


class CheckInOut(BaseModel):
    id: int
    equipo_id: int
    fecha_hora: Optional[datetime] = None
    kit_entregado: bool
    responsable: Optional[str] = None

    class Config:
        from_attributes = True


class ActualizarEstadoEquipo(BaseModel):
    estado: EstadoEquipoEnum
