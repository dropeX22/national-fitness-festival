"""
schemas.py
----------
Esquemas Pydantic: definen la "forma" de los datos que entran y salen de
la API (validación automática). No son tablas de BD, son solo estructuras
de datos para las peticiones HTTP.
"""

from pydantic import BaseModel, EmailStr, field_validator
from typing import List, Optional
from datetime import datetime, date
from app.models import (
    CategoriaEnum, GeneroEnum, EstadoEquipoEnum, EstadoPagoEnum,
    TallaEnum, TipoSangreEnum, MetodoPagoEnum,
)


# ---------------------------------------------------------------------------
# ATLETA
# ---------------------------------------------------------------------------

class AtletaCreate(BaseModel):
    nombre: str
    apellido: str
    cedula: str  # cédula o pasaporte
    fecha_nacimiento: date
    genero: GeneroEnum
    nacionalidad: str
    talla: TallaEnum
    box: Optional[str] = None
    tipo_sangre: TipoSangreEnum
    # Email y teléfono son opcionales aquí a nivel de campo individual,
    # porque solo el capitán los llena en el formulario — la obligatoriedad
    # PARA EL CAPITÁN se valida más abajo, en EquipoCreate.
    email: Optional[EmailStr] = None
    email_confirmacion: Optional[EmailStr] = None  # solo se usa para validar, no se guarda en BD
    telefono: Optional[str] = None
    es_capitan: bool = False  # marcamos cuál de los 4 es el capitán


class AtletaOut(BaseModel):
    id: int
    nombre: str
    apellido: str
    cedula: str
    fecha_nacimiento: date
    genero: GeneroEnum
    nacionalidad: str
    talla: TallaEnum
    box: Optional[str] = None
    tipo_sangre: TipoSangreEnum
    email: Optional[str] = None
    telefono: Optional[str] = None

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

        # El capitán es el único que llena email/teléfono en el formulario,
        # y son obligatorios para él porque es el contacto principal del
        # equipo (recibe correos y, si aplica, la solicitud de pago).
        capitan = capitanes[0]
        if not capitan.email or not capitan.email_confirmacion:
            raise ValueError("El capitán debe indicar su email y la confirmación de email")
        if capitan.email.strip().lower() != capitan.email_confirmacion.strip().lower():
            raise ValueError("El email y la confirmación de email del capitán no coinciden")
        if not (capitan.telefono or "").strip():
            raise ValueError("El capitán debe indicar un número de teléfono")

        cedulas = [a.cedula.strip() for a in atletas]
        if len(set(cedulas)) != len(cedulas):
            raise ValueError("No puede haber cédulas o pasaportes repetidos dentro del mismo equipo")

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


class AtletaUpdate(BaseModel):
    """
    Igual que AtletaCreate, pero se usa desde el panel admin para EDITAR
    integrantes de un equipo ya existente (no para el registro público).
    """
    nombre: str
    apellido: str
    cedula: str
    fecha_nacimiento: date
    genero: GeneroEnum
    nacionalidad: str
    talla: TallaEnum
    box: Optional[str] = None
    tipo_sangre: TipoSangreEnum
    email: Optional[EmailStr] = None
    telefono: Optional[str] = None
    es_capitan: bool = False


class EquipoUpdate(BaseModel):
    """
    Permite al staff del admin corregir un equipo ya inscrito (por ejemplo,
    si cambia un integrante). El participante NUNCA tiene acceso a este
    schema — solo se usa desde las rutas protegidas de /admin.
    """
    nombre: str
    categoria: CategoriaEnum
    atletas: List[AtletaUpdate]

    @field_validator("atletas")
    @classmethod
    def validar_equipo(cls, atletas: List[AtletaUpdate]):
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
            raise ValueError("No puede haber cédulas o pasaportes repetidos dentro del mismo equipo")
        return atletas


class EquipoCrearManual(EquipoUpdate):
    """
    Inscripción EXTRAORDINARIA de un equipo directamente desde el admin,
    saltándose el formulario público (por ejemplo, un equipo que se
    inscribió por WhatsApp o en persona).
    """
    pass


# ---------------------------------------------------------------------------
# PAGO
# ---------------------------------------------------------------------------

class PagoCreate(BaseModel):
    metodo_pago: MetodoPagoEnum
    # Solo obligatorio si metodo_pago == Yappy (se valida en la ruta, no aquí,
    # porque Pydantic no sabe todavía cuál método se eligió al validar el campo).
    telefono_yappy: Optional[str] = None


class PagoOut(BaseModel):
    id: int
    equipo_id: int
    monto: float
    metodo_pago: MetodoPagoEnum
    estado: EstadoPagoEnum
    fecha: datetime
    referencia_yappy: Optional[str] = None
    telefono_yappy: Optional[str] = None
    fecha_limite_verificacion: Optional[datetime] = None
    verificado_por: Optional[str] = None

    class Config:
        from_attributes = True


class VerificarTransferencia(BaseModel):
    responsable: str  # nombre del staff que verificó la transferencia


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
