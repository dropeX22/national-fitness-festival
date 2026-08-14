"""
routes/public.py
-----------------
Rutas públicas: la página de inicio, el formulario de registro de equipos
y la página de confirmación con el QR.
"""

import os
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pydantic import ValidationError

from app.database import get_db
from app import crud, schemas, models, utils

router = APIRouter(tags=["Público"])

CARPETA_ACTUAL = os.path.dirname(os.path.dirname(__file__))  # app/
templates = Jinja2Templates(directory=os.path.join(CARPETA_ACTUAL, "templates"))


@router.get("/", response_class=HTMLResponse)
def pagina_principal(request: Request, db: Session = Depends(get_db)):
    """Página de inicio: información del evento y botón para inscribirse."""
    evento = crud.obtener_o_crear_evento(db)
    total_equipos = len(crud.listar_equipos(db))
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "evento": evento, "total_equipos": total_equipos},
    )


@router.get("/registro", response_class=HTMLResponse)
def formulario_registro(request: Request):
    """Muestra el formulario de inscripción de equipo."""
    return templates.TemplateResponse("registro.html", {"request": request, "error": None})


@router.post("/registro", response_class=HTMLResponse)
async def procesar_registro(
    request: Request,
    db: Session = Depends(get_db),
    nombre_equipo: str = Form(...),
    categoria: str = Form(...),
    reglamento_aceptado: bool = Form(False),
    consentimiento_datos_aceptado: bool = Form(False),
    # El Atleta 1 SIEMPRE es el capitán — no se elige, es quien llena el
    # formulario. Por eso solo él tiene email/confirmación/teléfono.
    a1_nombre: str = Form(...), a1_apellido: str = Form(...), a1_cedula: str = Form(...),
    a1_fecha_nacimiento: str = Form(...), a1_genero: str = Form(...), a1_nacionalidad: str = Form(...),
    a1_talla: str = Form(...), a1_box: str = Form(""), a1_tipo_sangre: str = Form(...),
    a1_email: str = Form(...), a1_email_confirmacion: str = Form(...), a1_telefono: str = Form(...),
    a2_nombre: str = Form(...), a2_apellido: str = Form(...), a2_cedula: str = Form(...),
    a2_fecha_nacimiento: str = Form(...), a2_genero: str = Form(...), a2_nacionalidad: str = Form(...),
    a2_talla: str = Form(...), a2_box: str = Form(""), a2_tipo_sangre: str = Form(...),
    a3_nombre: str = Form(...), a3_apellido: str = Form(...), a3_cedula: str = Form(...),
    a3_fecha_nacimiento: str = Form(...), a3_genero: str = Form(...), a3_nacionalidad: str = Form(...),
    a3_talla: str = Form(...), a3_box: str = Form(""), a3_tipo_sangre: str = Form(...),
    a4_nombre: str = Form(...), a4_apellido: str = Form(...), a4_cedula: str = Form(...),
    a4_fecha_nacimiento: str = Form(...), a4_genero: str = Form(...), a4_nacionalidad: str = Form(...),
    a4_talla: str = Form(...), a4_box: str = Form(""), a4_tipo_sangre: str = Form(...),
):
    """
    Recibe el formulario de registro (equipo + 4 atletas), valida las
    reglas de negocio y crea el equipo en la base de datos.
    """
    atletas_form = [
        dict(nombre=a1_nombre, apellido=a1_apellido, cedula=a1_cedula, fecha_nacimiento=a1_fecha_nacimiento,
             genero=a1_genero, nacionalidad=a1_nacionalidad, talla=a1_talla, box=a1_box, tipo_sangre=a1_tipo_sangre,
             email=a1_email, email_confirmacion=a1_email_confirmacion, telefono=a1_telefono),
        dict(nombre=a2_nombre, apellido=a2_apellido, cedula=a2_cedula, fecha_nacimiento=a2_fecha_nacimiento,
             genero=a2_genero, nacionalidad=a2_nacionalidad, talla=a2_talla, box=a2_box, tipo_sangre=a2_tipo_sangre,
             email=None, email_confirmacion=None, telefono=None),
        dict(nombre=a3_nombre, apellido=a3_apellido, cedula=a3_cedula, fecha_nacimiento=a3_fecha_nacimiento,
             genero=a3_genero, nacionalidad=a3_nacionalidad, talla=a3_talla, box=a3_box, tipo_sangre=a3_tipo_sangre,
             email=None, email_confirmacion=None, telefono=None),
        dict(nombre=a4_nombre, apellido=a4_apellido, cedula=a4_cedula, fecha_nacimiento=a4_fecha_nacimiento,
             genero=a4_genero, nacionalidad=a4_nacionalidad, talla=a4_talla, box=a4_box, tipo_sangre=a4_tipo_sangre,
             email=None, email_confirmacion=None, telefono=None),
    ]

    try:
        atletas_schema = [
            schemas.AtletaCreate(**a, es_capitan=(idx == 0))  # el primero (índice 0) siempre es el capitán
            for idx, a in enumerate(atletas_form)
        ]

        datos_equipo = schemas.EquipoCreate(
            nombre=nombre_equipo,
            categoria=categoria,
            reglamento_aceptado=reglamento_aceptado,
            consentimiento_datos_aceptado=consentimiento_datos_aceptado,
            atletas=atletas_schema,
        )
    except ValidationError as error:
        mensaje = error.errors()[0]["msg"]
        return templates.TemplateResponse(
            "registro.html", {"request": request, "error": mensaje}
        )

    try:
        equipo = crud.crear_equipo(db, datos_equipo)
    except HTTPException as error:
        return templates.TemplateResponse(
            "registro.html", {"request": request, "error": error.detail}
        )

    # Generamos el QR del equipo apenas se crea (aunque el pago esté pendiente)
    utils.generar_qr_equipo(equipo.id, equipo.codigo)

    # Enviamos correo al capitán (modo simulado si no hay credenciales configuradas)
    capitan_atleta = equipo.capitan
    if capitan_atleta and capitan_atleta.email:
        ruta_local_qr = os.path.join(CARPETA_ACTUAL, "static", "qrcodes", f"{equipo.codigo}.png")
        utils.enviar_correo_confirmacion(
            destinatario=capitan_atleta.email,
            nombre_equipo=equipo.nombre,
            codigo_equipo=equipo.codigo,
            ruta_qr_local=ruta_local_qr,
        )

    return RedirectResponse(url=f"/confirmacion/{equipo.id}", status_code=303)


@router.get("/confirmacion/{equipo_id}", response_class=HTMLResponse)
def pagina_confirmacion(equipo_id: int, request: Request, db: Session = Depends(get_db)):
    """Muestra el estado del equipo, su QR, y el estado del pago (o las opciones para pagar)."""
    equipo = crud.obtener_equipo(db, equipo_id)
    ruta_qr = f"/static/qrcodes/{equipo.codigo}.png"
    evento = crud.obtener_o_crear_evento(db)

    # Tomamos el pago más reciente (si existe) para saber qué mostrar:
    # botones de pago (si no hay ninguno), "esperando verificación" (si es
    # transferencia pendiente), o "pagado" (si ya se confirmó).
    pagos = crud.obtener_pagos_de_equipo(db, equipo_id)
    ultimo_pago = pagos[-1] if pagos else None

    return templates.TemplateResponse(
        "confirmacion.html",
        {
            "request": request,
            "equipo": equipo,
            "ruta_qr": ruta_qr,
            "evento": evento,
            "pago": ultimo_pago,
        },
    )


@router.get("/privacidad", response_class=HTMLResponse)
def pagina_privacidad(request: Request):
    """Aviso de privacidad — Ley 81 de 2019, Panamá."""
    return templates.TemplateResponse("privacidad.html", {"request": request})
