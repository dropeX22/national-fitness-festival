"""
routes/admin.py
----------------
Panel de administración: listar equipos con filtros, cambiar estado,
exportar a Excel y ver estadísticas (dashboard).

NOTA DE SEGURIDAD: para simplificar el proyecto de estudiante, este panel
NO tiene autenticación real. En producción se debe proteger con login
(por ejemplo con fastapi-login o HTTPBasic) antes de desplegarlo público.
"""

import os
import io
from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app import crud, schemas, models
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
        "Código Equipo", "Nombre Equipo", "Categoría", "Estado", "Atleta",
        "Cédula", "Género", "Email", "Teléfono", "Es Capitán",
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
                atleta.cedula,
                atleta.genero.value if hasattr(atleta.genero, "value") else atleta.genero,
                atleta.email,
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
