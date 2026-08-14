"""
crud.py
-------
Funciones que hablan directamente con la base de datos (Create, Read,
Update, Delete). Las rutas (routes/*.py) llaman a estas funciones en
lugar de escribir consultas SQLAlchemy directamente, para mantener el
código organizado.
"""

import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException

from app import models, schemas


# ---------------------------------------------------------------------------
# EVENTO
# ---------------------------------------------------------------------------

def obtener_o_crear_evento(db: Session) -> models.Evento:
    """
    Devuelve el evento ACTIVO (el de este año). Si nunca se ha creado
    ninguno, crea uno por defecto y lo marca como activo.
    """
    evento = db.query(models.Evento).filter(models.Evento.activo == True).first()  # noqa: E712
    if not evento:
        evento = models.Evento(
            nombre="National Fitness Festival",
            fecha=datetime.datetime(2026, 11, 15, 8, 0),
            descripcion="Competencia de CrossFit por equipos en Panamá.",
            precio_inscripcion=200.0,
            activo=True,
        )
        db.add(evento)
        db.commit()
        db.refresh(evento)
    return evento


def crear_nuevo_evento_anual(db: Session, nombre: str, fecha: datetime.datetime, precio: float, descripcion: str = "") -> models.Evento:
    """
    Cierra el evento activo actual (pasa a activo=False, queda como
    historial con sus equipos y atletas intactos) y crea uno nuevo que
    pasa a ser el activo. A partir de ese momento, todas las inscripciones
    nuevas (y la restricción de cédula única) aplican sobre este evento
    nuevo — los atletas del año pasado pueden volver a inscribirse sin
    problema, porque su cédula quedó asociada al evento_id anterior.
    """
    evento_anterior = db.query(models.Evento).filter(models.Evento.activo == True).first()  # noqa: E712
    if evento_anterior:
        evento_anterior.activo = False

    nuevo_evento = models.Evento(
        nombre=nombre,
        fecha=fecha,
        descripcion=descripcion,
        precio_inscripcion=precio,
        activo=True,
    )
    db.add(nuevo_evento)
    db.commit()
    db.refresh(nuevo_evento)
    return nuevo_evento


# ---------------------------------------------------------------------------
# EQUIPO
# ---------------------------------------------------------------------------

def generar_codigo_equipo(db: Session) -> str:
    """Genera un código único incremental tipo NF-001, NF-002, ..."""
    total = db.query(func.count(models.Equipo.id)).scalar() or 0
    siguiente = total + 1
    codigo = f"NF-{siguiente:03d}"
    # Por seguridad, si ya existiera (equipo borrado de por medio), seguimos subiendo
    while db.query(models.Equipo).filter(models.Equipo.codigo == codigo).first():
        siguiente += 1
        codigo = f"NF-{siguiente:03d}"
    return codigo


def validar_atletas_disponibles(db: Session, cedulas: list[str], evento_id: int):
    """
    Verifica las reglas de negocio antes de crear el equipo:
    - Cédula no inscrita ya en NINGÚN equipo DE ESTE MISMO EVENTO.
    - La misma cédula SÍ puede existir en eventos anteriores (otros años);
      eso es correcto y esperado, no es un duplicado.
    """
    existentes = (
        db.query(models.Atleta)
        .filter(models.Atleta.cedula.in_(cedulas), models.Atleta.evento_id == evento_id)
        .all()
    )
    if existentes:
        nombres = ", ".join([f"{a.nombre} {a.apellido} ({a.cedula})" for a in existentes])
        raise HTTPException(
            status_code=400,
            detail=f"Los siguientes atletas ya están inscritos en otro equipo de este evento: {nombres}",
        )


def crear_equipo(db: Session, datos: schemas.EquipoCreate) -> models.Equipo:
    """Crea el equipo junto con sus 4 atletas y define al capitán."""
    evento = obtener_o_crear_evento(db)

    cedulas = [a.cedula.strip() for a in datos.atletas]
    validar_atletas_disponibles(db, cedulas, evento.id)

    codigo = generar_codigo_equipo(db)

    nuevo_equipo = models.Equipo(
        codigo=codigo,
        nombre=datos.nombre.strip(),
        categoria=datos.categoria,
        reglamento_aceptado=datos.reglamento_aceptado,
        consentimiento_datos_aceptado=datos.consentimiento_datos_aceptado,
        estado=models.EstadoEquipoEnum.pendiente,
        evento_id=evento.id,
    )
    db.add(nuevo_equipo)
    db.flush()  # asigna un ID al equipo sin cerrar la transacción todavía

    capitan_atleta = None
    for atleta_data in datos.atletas:
        atleta = models.Atleta(
            nombre=atleta_data.nombre.strip(),
            apellido=atleta_data.apellido.strip(),
            cedula=atleta_data.cedula.strip(),
            fecha_nacimiento=atleta_data.fecha_nacimiento,
            genero=atleta_data.genero,
            nacionalidad=atleta_data.nacionalidad.strip(),
            talla=atleta_data.talla,
            box=(atleta_data.box or "").strip() or None,
            tipo_sangre=atleta_data.tipo_sangre,
            # Email y teléfono solo se guardan para el capitán; para los
            # demás integrantes el formulario no los pide, así que quedan NULL.
            email=atleta_data.email if atleta_data.es_capitan else None,
            telefono=atleta_data.telefono if atleta_data.es_capitan else None,
            equipo_id=nuevo_equipo.id,
            evento_id=evento.id,  # necesario para que la restricción única (cedula, evento_id) funcione
        )
        db.add(atleta)
        db.flush()
        if atleta_data.es_capitan:
            capitan_atleta = atleta

    nuevo_equipo.capitan_id = capitan_atleta.id
    db.commit()
    db.refresh(nuevo_equipo)
    return nuevo_equipo


def crear_equipo_manual_admin(db: Session, datos: schemas.EquipoCrearManual) -> models.Equipo:
    """
    Igual que crear_equipo(), pero para inscripciones EXTRAORDINARIAS que
    el staff registra directamente desde el panel admin (equipos que se
    inscribieron por otro medio, ej. WhatsApp o en persona). No exige
    email/confirmación del capitán con el mismo rigor que el formulario
    público, porque aquí es el staff quien transcribe los datos.
    """
    evento = obtener_o_crear_evento(db)
    cedulas = [a.cedula.strip() for a in datos.atletas]
    validar_atletas_disponibles(db, cedulas, evento.id)

    codigo = generar_codigo_equipo(db)
    nuevo_equipo = models.Equipo(
        codigo=codigo,
        nombre=datos.nombre.strip(),
        categoria=datos.categoria,
        reglamento_aceptado=True,  # el staff asume la responsabilidad al inscribir manualmente
        consentimiento_datos_aceptado=True,
        estado=models.EstadoEquipoEnum.pendiente,
        evento_id=evento.id,
    )
    db.add(nuevo_equipo)
    db.flush()

    capitan_atleta = None
    for atleta_data in datos.atletas:
        atleta = models.Atleta(
            nombre=atleta_data.nombre.strip(),
            apellido=atleta_data.apellido.strip(),
            cedula=atleta_data.cedula.strip(),
            fecha_nacimiento=atleta_data.fecha_nacimiento,
            genero=atleta_data.genero,
            nacionalidad=atleta_data.nacionalidad.strip(),
            talla=atleta_data.talla,
            box=(atleta_data.box or "").strip() or None,
            tipo_sangre=atleta_data.tipo_sangre,
            email=atleta_data.email if atleta_data.es_capitan else None,
            telefono=atleta_data.telefono if atleta_data.es_capitan else None,
            equipo_id=nuevo_equipo.id,
            evento_id=evento.id,
        )
        db.add(atleta)
        db.flush()
        if atleta_data.es_capitan:
            capitan_atleta = atleta

    nuevo_equipo.capitan_id = capitan_atleta.id
    db.commit()
    db.refresh(nuevo_equipo)
    return nuevo_equipo


def editar_equipo(db: Session, equipo_id: int, datos: schemas.EquipoUpdate) -> models.Equipo:
    """
    Permite al staff corregir los integrantes de un equipo ya inscrito
    (ej. si cambia una persona). Borra los 4 atletas viejos y crea los 4
    nuevos — más simple y menos propenso a errores que tratar de
    "adivinar" cuál atleta corresponde a cuál fila del formulario editado.
    """
    equipo = obtener_equipo(db, equipo_id)
    evento_id = equipo.evento_id

    # Verificamos cédulas duplicadas contra OTROS equipos (excluyendo este mismo)
    cedulas_nuevas = [a.cedula.strip() for a in datos.atletas]
    conflicto = (
        db.query(models.Atleta)
        .filter(
            models.Atleta.cedula.in_(cedulas_nuevas),
            models.Atleta.evento_id == evento_id,
            models.Atleta.equipo_id != equipo_id,
        )
        .all()
    )
    if conflicto:
        nombres = ", ".join([f"{a.nombre} {a.apellido} ({a.cedula})" for a in conflicto])
        raise HTTPException(
            status_code=400,
            detail=f"Estas cédulas ya pertenecen a otro equipo de este evento: {nombres}",
        )

    equipo.nombre = datos.nombre.strip()
    equipo.categoria = datos.categoria

    # Quitamos temporalmente la referencia al capitán antes de borrar los
    # atletas viejos, porque capitan_id apunta a uno de ellos.
    equipo.capitan_id = None
    db.flush()
    for atleta_viejo in list(equipo.atletas):
        db.delete(atleta_viejo)
    db.flush()

    capitan_atleta = None
    for atleta_data in datos.atletas:
        atleta = models.Atleta(
            nombre=atleta_data.nombre.strip(),
            apellido=atleta_data.apellido.strip(),
            cedula=atleta_data.cedula.strip(),
            fecha_nacimiento=atleta_data.fecha_nacimiento,
            genero=atleta_data.genero,
            nacionalidad=atleta_data.nacionalidad.strip(),
            talla=atleta_data.talla,
            box=(atleta_data.box or "").strip() or None,
            tipo_sangre=atleta_data.tipo_sangre,
            email=atleta_data.email if atleta_data.es_capitan else None,
            telefono=atleta_data.telefono if atleta_data.es_capitan else None,
            equipo_id=equipo.id,
            evento_id=evento_id,
        )
        db.add(atleta)
        db.flush()
        if atleta_data.es_capitan:
            capitan_atleta = atleta

    equipo.capitan_id = capitan_atleta.id
    db.commit()
    db.refresh(equipo)
    return equipo


def obtener_equipo(db: Session, equipo_id: int) -> models.Equipo:
    equipo = db.query(models.Equipo).filter(models.Equipo.id == equipo_id).first()
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    return equipo


def obtener_equipo_por_codigo_o_nombre(db: Session, termino: str) -> models.Equipo | None:
    termino = termino.strip()
    equipo = (
        db.query(models.Equipo)
        .filter(
            (models.Equipo.codigo.ilike(f"%{termino}%"))
            | (models.Equipo.nombre.ilike(f"%{termino}%"))
        )
        .first()
    )
    return equipo


def listar_equipos(
    db: Session,
    categoria: str | None = None,
    estado: str | None = None,
):
    query = db.query(models.Equipo)
    if categoria:
        query = query.filter(models.Equipo.categoria == categoria)
    if estado:
        query = query.filter(models.Equipo.estado == estado)
    return query.order_by(models.Equipo.id.asc()).all()


def actualizar_estado_equipo(db: Session, equipo_id: int, estado: str) -> models.Equipo:
    equipo = obtener_equipo(db, equipo_id)
    equipo.estado = estado
    db.commit()
    db.refresh(equipo)
    return equipo


# ---------------------------------------------------------------------------
# PAGO
# ---------------------------------------------------------------------------

HORAS_PLAZO_VERIFICACION_TRANSFERENCIA = 72  # definido con el organizador del evento


def crear_pago(db: Session, equipo_id: int, monto: float, metodo_pago: models.MetodoPagoEnum, telefono_yappy: str | None = None) -> models.Pago:
    """
    Crea el registro de pago para un equipo, con un comportamiento distinto
    según el método elegido:
    - Yappy: queda "Pendiente" (esperando que el usuario complete el pago
      en la app de Yappy, o lo simule en modo de pruebas).
    - Transferencia: queda "Pendiente de verificación" con un plazo límite
      (HORAS_PLAZO_VERIFICACION_TRANSFERENCIA) para que el staff la revise
      manualmente contra el estado de cuenta del banco.
    """
    equipo = obtener_equipo(db, equipo_id)

    # Evitamos crear pagos duplicados si ya existe uno confirmado
    pago_confirmado = (
        db.query(models.Pago)
        .filter(models.Pago.equipo_id == equipo_id, models.Pago.estado == models.EstadoPagoEnum.confirmado)
        .first()
    )
    if pago_confirmado:
        raise HTTPException(status_code=400, detail="Este equipo ya tiene un pago confirmado")

    if metodo_pago == models.MetodoPagoEnum.yappy:
        if not (telefono_yappy or "").strip():
            raise HTTPException(status_code=400, detail="Debes indicar el número de teléfono para la solicitud de Yappy")
        estado_inicial = models.EstadoPagoEnum.pendiente
        referencia = f"YAPPY-{equipo.codigo}-{int(datetime.datetime.utcnow().timestamp())}"
        fecha_limite = None
    else:  # transferencia
        estado_inicial = models.EstadoPagoEnum.pendiente_verificacion
        referencia = None
        fecha_limite = datetime.datetime.utcnow() + datetime.timedelta(hours=HORAS_PLAZO_VERIFICACION_TRANSFERENCIA)

    pago = models.Pago(
        equipo_id=equipo.id,
        monto=monto,
        metodo_pago=metodo_pago,
        estado=estado_inicial,
        referencia_yappy=referencia,
        telefono_yappy=telefono_yappy if metodo_pago == models.MetodoPagoEnum.yappy else None,
        fecha_limite_verificacion=fecha_limite,
    )
    db.add(pago)
    db.commit()
    db.refresh(pago)
    return pago


def verificar_transferencia_manual(db: Session, pago_id: int, responsable: str) -> models.Pago:
    """
    El staff confirma, desde el admin, que revisó el estado de cuenta del
    banco y la transferencia sí llegó. Marca el pago como Confirmado y el
    equipo como Pagado — el correo de confirmación (correo 2) se envía
    desde la ruta, no aquí (crud.py no debe encargarse de enviar correos).
    """
    pago = db.query(models.Pago).filter(models.Pago.id == pago_id).first()
    if not pago:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    if pago.metodo_pago != models.MetodoPagoEnum.transferencia:
        raise HTTPException(status_code=400, detail="Este pago no es por transferencia")
    if pago.estado == models.EstadoPagoEnum.confirmado:
        return pago  # ya estaba confirmado, no hacemos nada más (evita duplicar correos)

    pago.estado = models.EstadoPagoEnum.confirmado
    pago.verificado_por = responsable
    db.commit()
    db.refresh(pago)

    equipo = obtener_equipo(db, pago.equipo_id)
    equipo.estado = models.EstadoEquipoEnum.pagado
    db.commit()

    return pago


def confirmar_pago_por_referencia(db: Session, referencia_yappy: str, estado_nuevo: str, monto: float) -> models.Pago:
    pago = (
        db.query(models.Pago)
        .filter(models.Pago.referencia_yappy == referencia_yappy)
        .first()
    )
    if not pago:
        raise HTTPException(status_code=404, detail="Referencia de pago no encontrada")

    # Manejo de pagos duplicados: si ya estaba confirmado, no hacemos nada más
    if pago.estado == models.EstadoPagoEnum.confirmado:
        return pago

    pago.estado = estado_nuevo
    pago.monto = monto
    db.commit()
    db.refresh(pago)

    # Si el pago fue confirmado, el equipo pasa a estado "Pagado" automáticamente
    if estado_nuevo == models.EstadoPagoEnum.confirmado:
        equipo = obtener_equipo(db, pago.equipo_id)
        equipo.estado = models.EstadoEquipoEnum.pagado
        db.commit()

    return pago


def obtener_pagos_de_equipo(db: Session, equipo_id: int):
    return db.query(models.Pago).filter(models.Pago.equipo_id == equipo_id).all()


# ---------------------------------------------------------------------------
# CHECK-IN
# ---------------------------------------------------------------------------

def obtener_o_crear_checkin(db: Session, equipo_id: int) -> models.CheckIn:
    checkin = db.query(models.CheckIn).filter(models.CheckIn.equipo_id == equipo_id).first()
    if not checkin:
        checkin = models.CheckIn(equipo_id=equipo_id, kit_entregado=False)
        db.add(checkin)
        db.commit()
        db.refresh(checkin)
    return checkin


def registrar_checkin(db: Session, equipo_id: int, responsable: str, kit_entregado: bool) -> models.CheckIn:
    equipo = obtener_equipo(db, equipo_id)

    if equipo.estado != models.EstadoEquipoEnum.pagado:
        raise HTTPException(
            status_code=400,
            detail="El equipo no tiene el pago confirmado, no puede hacer check-in",
        )

    checkin = obtener_o_crear_checkin(db, equipo_id)
    checkin.fecha_hora = datetime.datetime.utcnow()
    checkin.kit_entregado = kit_entregado
    checkin.responsable = responsable
    db.commit()
    db.refresh(checkin)
    return checkin


# ---------------------------------------------------------------------------
# DASHBOARD / ESTADÍSTICAS
# ---------------------------------------------------------------------------

def obtener_estadisticas(db: Session) -> dict:
    total_equipos = db.query(func.count(models.Equipo.id)).scalar() or 0
    equipos_pagados = (
        db.query(func.count(models.Equipo.id))
        .filter(models.Equipo.estado == models.EstadoEquipoEnum.pagado)
        .scalar()
        or 0
    )
    equipos_pendientes = (
        db.query(func.count(models.Equipo.id))
        .filter(models.Equipo.estado == models.EstadoEquipoEnum.pendiente)
        .scalar()
        or 0
    )
    total_atletas = db.query(func.count(models.Atleta.id)).scalar() or 0
    total_checkins = (
        db.query(func.count(models.CheckIn.id))
        .filter(models.CheckIn.fecha_hora.isnot(None))
        .scalar()
        or 0
    )
    recaudado = (
        db.query(func.coalesce(func.sum(models.Pago.monto), 0.0))
        .filter(models.Pago.estado == models.EstadoPagoEnum.confirmado)
        .scalar()
        or 0.0
    )

    por_categoria = (
        db.query(models.Equipo.categoria, func.count(models.Equipo.id))
        .group_by(models.Equipo.categoria)
        .all()
    )

    return {
        "total_equipos": total_equipos,
        "equipos_pagados": equipos_pagados,
        "equipos_pendientes": equipos_pendientes,
        "total_atletas": total_atletas,
        "total_checkins": total_checkins,
        "recaudado": recaudado,
        "por_categoria": {str(cat.value if hasattr(cat, "value") else cat): cant for cat, cant in por_categoria},
    }
