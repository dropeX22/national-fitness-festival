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
    # Atleta 1 (capitán por defecto en el form, pero se puede marcar otro)
    a1_nombre: str = Form(...),
    a1_cedula: str = Form(...),
    a1_email: str = Form(...),
    a1_telefono: str = Form(""),
    a1_genero: str = Form(...),
    a2_nombre: str = Form(...),
    a2_cedula: str = Form(...),
    a2_email: str = Form(...),
    a2_telefono: str = Form(""),
    a2_genero: str = Form(...),
    a3_nombre: str = Form(...),
    a3_cedula: str = Form(...),
    a3_email: str = Form(...),
    a3_telefono: str = Form(""),
    a3_genero: str = Form(...),
    a4_nombre: str = Form(...),
    a4_cedula: str = Form(...),
    a4_email: str = Form(...),
    a4_telefono: str = Form(""),
    a4_genero: str = Form(...),
    capitan: int = Form(...),  # número del 1 al 4 indicando quién es el capitán
):
    """
    Recibe el formulario de registro (equipo + 4 atletas), valida las
    reglas de negocio y crea el equipo en la base de datos.
    """
    atletas_form = [
        {"nombre": a1_nombre, "cedula": a1_cedula, "email": a1_email, "telefono": a1_telefono, "genero": a1_genero},
        {"nombre": a2_nombre, "cedula": a2_cedula, "email": a2_email, "telefono": a2_telefono, "genero": a2_genero},
        {"nombre": a3_nombre, "cedula": a3_cedula, "email": a3_email, "telefono": a3_telefono, "genero": a3_genero},
        {"nombre": a4_nombre, "cedula": a4_cedula, "email": a4_email, "telefono": a4_telefono, "genero": a4_genero},
    ]

    try:
        atletas_schema = [
            schemas.AtletaCreate(
                nombre=a["nombre"],
                cedula=a["cedula"],
                email=a["email"],
                telefono=a["telefono"],
                genero=a["genero"],
                es_capitan=(idx + 1 == capitan),
            )
            for idx, a in enumerate(atletas_form)
        ]

        datos_equipo = schemas.EquipoCreate(
            nombre=nombre_equipo,
            categoria=categoria,
            reglamento_aceptado=reglamento_aceptado,
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
    ruta_qr = utils.generar_qr_equipo(equipo.id, equipo.codigo)

    # Enviamos correo al capitán (modo simulado si no hay credenciales configuradas)
    capitan_atleta = equipo.capitan
    if capitan_atleta:
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
    """Muestra el estado del equipo, su QR y el botón de pago."""
    equipo = crud.obtener_equipo(db, equipo_id)
    ruta_qr = f"/static/qrcodes/{equipo.codigo}.png"
    evento = crud.obtener_o_crear_evento(db)

    return templates.TemplateResponse(
        "confirmacion.html",
        {
            "request": request,
            "equipo": equipo,
            "ruta_qr": ruta_qr,
            "evento": evento,
        },
    )
