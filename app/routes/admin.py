"""
routes/admin.py
----------------
Panel de administración: listar equipos con filtros, editar o crear
equipos manualmente, verificar transferencias, exportar a Excel y ver
estadísticas (dashboard). Todas las rutas están protegidas con usuario y
contraseña (ver app/auth.py).
"""

import os
import io
from fastapi import APIRouter, Request, Depends, Query, Form
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pydantic import ValidationError

from app.database import get_db
from app import crud, schemas, models, utils
from app.auth import verificar_credenciales

# El parámetro "dependencies" aplica verificar_credenciales a TODAS las rutas
# de este router automáticamente. No hace falta escribir Depends(...) en
# cada función de abajo — FastAPI lo ejecuta antes de entrar a cualquiera
# de ellas, y si falla, ni siquiera llega a correr el código de la ruta.
router = APIRouter(prefix="/admin", tags=["Administración"], dependencies=[Depends(verificar_credenciales)])

CARPETA_ACTUAL = os.path.dirname(os.path.dirname(__file__))
templates = Jinja2Templates(directory=os.path.join(CARPETA_ACTUAL, "templates"))


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def panel_admin(
    request: Request,
    db: Session = Depends(get_db),
    categoria: str | None = Query(None),
    estado: str | None = Query(None),
):
    """Muestra la tabla de equipos inscritos con filtros opcionales."""
    equipos = crud.listar_equipos(db, categoria=categoria, estado=estado)
    estadisticas = crud.obtener_estadisticas(db)

    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "equipos": equipos,
            "estadisticas": estadisticas,
            "categoria_filtro": categoria or "",
            "estado_filtro": estado or "",
        },
    )


@router.get("/equipos", response_model=list[schemas.EquipoOut])
def api_listar_equipos(
    db: Session = Depends(get_db),
    categoria: str | None = Query(None),
    estado: str | None = Query(None),
):
    """Versión JSON del listado (útil para integraciones o pruebas)."""
    return crud.listar_equipos(db, categoria=categoria, estado=estado)


@router.put("/equipo/{equipo_id}/estado", response_model=schemas.EquipoOut)
def api_actualizar_estado(
    equipo_id: int,
    datos: schemas.ActualizarEstadoEquipo,
    db: Session = Depends(get_db),
):
    """Cambia manualmente el estado de un equipo (ej: confirmar pago a mano)."""
    return crud.actualizar_estado_equipo(db, equipo_id, datos.estado)


def _leer_atletas_del_formulario(form) -> list[dict]:
    """
    Extrae los 4 bloques de atleta (a1_..., a2_..., a3_..., a4_...) de un
    formulario HTML, igual que hace public.py para el registro. Se
    reutiliza tanto para editar como para crear equipos manualmente.
    """
    atletas = []
    for n in range(1, 5):
        atletas.append(dict(
            nombre=form.get(f"a{n}_nombre", ""),
            apellido=form.get(f"a{n}_apellido", ""),
            cedula=form.get(f"a{n}_cedula", ""),
            fecha_nacimiento=form.get(f"a{n}_fecha_nacimiento", ""),
            genero=form.get(f"a{n}_genero", ""),
            nacionalidad=form.get(f"a{n}_nacionalidad", ""),
            talla=form.get(f"a{n}_talla", ""),
            box=form.get(f"a{n}_box", "") or None,
            tipo_sangre=form.get(f"a{n}_tipo_sangre", ""),
            email=form.get(f"a{n}_email", "") or None,
            telefono=form.get(f"a{n}_telefono", "") or None,
            es_capitan=(n == 1),  # el Atleta 1 siempre es el capitán, igual que en el registro público
        ))
    return atletas


def _atletas_para_formulario(equipo) -> list[dict]:
    """
    Convierte los 4 objetos Atleta de un equipo en una lista simple de
    diccionarios, con la fecha en formato de texto (YYYY-MM-DD, el que
    espera un <input type="date">) para poder precargar el formulario
    de edición fácilmente desde Jinja2.
    """
    if not equipo:
        return [dict(nombre="", apellido="", cedula="", fecha_nacimiento="", genero="M",
                      nacionalidad="", talla="M", box="", tipo_sangre="O+", email="", telefono="")
                for n in range(1, 5)]

    # El capitán siempre va primero (posición 1 del formulario), y los
    # otros 3 después, ordenados por id para que el orden sea estable.
    capitan = next((a for a in equipo.atletas if a.id == equipo.capitan_id), None)
    resto = sorted([a for a in equipo.atletas if a.id != equipo.capitan_id], key=lambda a: a.id)
    atletas_ordenados = ([capitan] if capitan else []) + resto

    return [
        dict(
            nombre=a.nombre, apellido=a.apellido, cedula=a.cedula,
            fecha_nacimiento=a.fecha_nacimiento.isoformat() if a.fecha_nacimiento else "",
            genero=a.genero.value, nacionalidad=a.nacionalidad, talla=a.talla.value,
            box=a.box or "", tipo_sangre=a.tipo_sangre.value,
            email=a.email or "", telefono=a.telefono or "",
        )
        for a in atletas_ordenados
    ]


@router.get("/equipo/{equipo_id}/editar", response_class=HTMLResponse)
def formulario_editar_equipo(equipo_id: int, request: Request, db: Session = Depends(get_db)):
    """Muestra el formulario de edición, precargado con los datos actuales del equipo."""
    equipo = crud.obtener_equipo(db, equipo_id)
    return templates.TemplateResponse(
        "admin_equipo_form.html",
        {
            "request": request, "equipo": equipo, "modo": "editar", "error": None,
            "atletas_valores": _atletas_para_formulario(equipo),
            "nombre_equipo_valor": equipo.nombre,
            "categoria_valor": equipo.categoria.value,
        },
    )


@router.post("/equipo/{equipo_id}/editar", response_class=HTMLResponse)
async def procesar_editar_equipo(equipo_id: int, request: Request, db: Session = Depends(get_db)):
    """Aplica los cambios hechos por el staff a un equipo ya inscrito."""
    form = await request.form()
    atletas_form = _leer_atletas_del_formulario(form)

    try:
        atletas_schema = [schemas.AtletaUpdate(**a) for a in atletas_form]
        datos = schemas.EquipoUpdate(
            nombre=form.get("nombre_equipo", ""),
            categoria=form.get("categoria", ""),
            atletas=atletas_schema,
        )
        equipo = crud.editar_equipo(db, equipo_id, datos)
    except ValidationError as error:
        equipo_actual = crud.obtener_equipo(db, equipo_id)
        return templates.TemplateResponse(
            "admin_equipo_form.html",
            {
                "request": request, "equipo": equipo_actual, "modo": "editar",
                "error": error.errors()[0]["msg"],
                "atletas_valores": [{**a, "box": a["box"] or "", "email": a["email"] or "", "telefono": a["telefono"] or ""} for a in atletas_form],
                "nombre_equipo_valor": form.get("nombre_equipo", ""),
                "categoria_valor": form.get("categoria", ""),
            },
        )
    except Exception as error:
        equipo_actual = crud.obtener_equipo(db, equipo_id)
        detalle = getattr(error, "detail", str(error))
        return templates.TemplateResponse(
            "admin_equipo_form.html",
            {
                "request": request, "equipo": equipo_actual, "modo": "editar", "error": detalle,
                "atletas_valores": [{**a, "box": a["box"] or "", "email": a["email"] or "", "telefono": a["telefono"] or ""} for a in atletas_form],
                "nombre_equipo_valor": form.get("nombre_equipo", ""),
                "categoria_valor": form.get("categoria", ""),
            },
        )

    return RedirectResponse(url="/admin", status_code=303)


@router.get("/equipo/nuevo", response_class=HTMLResponse)
def formulario_crear_equipo_manual(request: Request):
    """Formulario en blanco para inscripción extraordinaria desde el admin."""
    return templates.TemplateResponse(
        "admin_equipo_form.html",
        {
            "request": request, "equipo": None, "modo": "crear", "error": None,
            "atletas_valores": _atletas_para_formulario(None),
            "nombre_equipo_valor": "", "categoria_valor": "",
        },
    )


@router.post("/equipo/nuevo", response_class=HTMLResponse)
async def procesar_crear_equipo_manual(request: Request, db: Session = Depends(get_db)):
    """Crea un equipo directamente desde el admin, sin pasar por el formulario público."""
    form = await request.form()
    atletas_form = _leer_atletas_del_formulario(form)

    try:
        atletas_schema = [schemas.AtletaUpdate(**a) for a in atletas_form]
        datos = schemas.EquipoCrearManual(
            nombre=form.get("nombre_equipo", ""),
            categoria=form.get("categoria", ""),
            atletas=atletas_schema,
        )
        equipo = crud.crear_equipo_manual_admin(db, datos)
    except ValidationError as error:
        return templates.TemplateResponse(
            "admin_equipo_form.html",
            {
                "request": request, "equipo": None, "modo": "crear",
                "error": error.errors()[0]["msg"],
                "atletas_valores": [{**a, "box": a["box"] or "", "email": a["email"] or "", "telefono": a["telefono"] or ""} for a in atletas_form],
                "nombre_equipo_valor": form.get("nombre_equipo", ""),
                "categoria_valor": form.get("categoria", ""),
            },
        )
    except Exception as error:
        detalle = getattr(error, "detail", str(error))
        return templates.TemplateResponse(
            "admin_equipo_form.html",
            {
                "request": request, "equipo": None, "modo": "crear", "error": detalle,
                "atletas_valores": [{**a, "box": a["box"] or "", "email": a["email"] or "", "telefono": a["telefono"] or ""} for a in atletas_form],
                "nombre_equipo_valor": form.get("nombre_equipo", ""),
                "categoria_valor": form.get("categoria", ""),
            },
        )

    utils.generar_qr_equipo(equipo.id, equipo.codigo)
    return RedirectResponse(url="/admin", status_code=303)


@router.post("/pago/{pago_id}/verificar-transferencia")
def verificar_transferencia(pago_id: int, db: Session = Depends(get_db), responsable: str = Form(...)):
    """
    El staff confirma que revisó el estado de cuenta del banco y la
    transferencia sí llegó. Dispara el correo 2 (confirmación) al capitán.
    """
    pago = crud.verificar_transferencia_manual(db, pago_id, responsable)
    equipo = crud.obtener_equipo(db, pago.equipo_id)

    capitan = equipo.capitan
    if capitan and capitan.email:
        utils.enviar_correo_transferencia_confirmada(
            destinatario=capitan.email,
            nombre_equipo=equipo.nombre,
            codigo_equipo=equipo.codigo,
        )

    return RedirectResponse(url="/admin", status_code=303)


@router.get("/exportar-excel")
def exportar_excel(db: Session = Depends(get_db)):
    """Genera un archivo Excel (.xlsx) con todos los equipos y atletas."""
    import openpyxl
    from openpyxl.styles import Font

    equipos = crud.listar_equipos(db)

    wb = openpyxl.Workbook()
    hoja = wb.active
    hoja.title = "Inscripciones"

    encabezados = [
        "Código Equipo", "Nombre Equipo", "Categoría", "Estado", "Nombre", "Apellido",
        "Cédula/Pasaporte", "F. Nacimiento", "Género", "Nacionalidad", "Talla", "Box",
        "Tipo de Sangre", "Email", "Teléfono", "Es Capitán",
    ]
    hoja.append(encabezados)
    for celda in hoja[1]:
        celda.font = Font(bold=True)

    for equipo in equipos:
        for atleta in equipo.atletas:
            hoja.append([
                equipo.codigo,
                equipo.nombre,
                equipo.categoria.value if hasattr(equipo.categoria, "value") else equipo.categoria,
                equipo.estado.value if hasattr(equipo.estado, "value") else equipo.estado,
                atleta.nombre,
                atleta.apellido,
                atleta.cedula,
                atleta.fecha_nacimiento.strftime("%d/%m/%Y") if atleta.fecha_nacimiento else "",
                atleta.genero.value if hasattr(atleta.genero, "value") else atleta.genero,
                atleta.nacionalidad,
                atleta.talla.value if hasattr(atleta.talla, "value") else atleta.talla,
                atleta.box or "",
                atleta.tipo_sangre.value if hasattr(atleta.tipo_sangre, "value") else atleta.tipo_sangre,
                atleta.email or "",
                atleta.telefono or "",
                "Sí" if equipo.capitan_id == atleta.id else "No",
            ])

    # Ajustar ancho de columnas automáticamente (aproximado)
    for columna in hoja.columns:
        max_len = max(len(str(c.value)) if c.value else 0 for c in columna)
        hoja.column_dimensions[columna[0].column_letter].width = max_len + 2

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=inscripciones_national_fitness_festival.xlsx"},
    )


@router.get("/dashboard", response_model=dict)
def api_dashboard(db: Session = Depends(get_db)):
    """Estadísticas simples: total inscritos, pagados, recaudado, etc."""
    return crud.obtener_estadisticas(db)
