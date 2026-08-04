"""
routes/checkin.py
------------------
Rutas para el check-in del día del evento: buscar equipo (por nombre,
código o contenido del QR escaneado) y registrar la entrega del kit.
"""

import os
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app import crud, schemas, models, utils
from app.auth import verificar_credenciales

# Igual que en admin.py: protegemos TODAS las rutas de check-in, porque
# ahí también se ven cédulas y datos personales de los atletas, y solo
# el staff del evento debería poder buscar equipos y entregar kits.
router = APIRouter(prefix="/checkin", tags=["Check-in"], dependencies=[Depends(verificar_credenciales)])

CARPETA_ACTUAL = os.path.dirname(os.path.dirname(__file__))
templates = Jinja2Templates(directory=os.path.join(CARPETA_ACTUAL, "templates"))


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def pagina_checkin(request: Request):
    """Página con buscador y (opcionalmente) escáner QR para el staff."""
    return templates.TemplateResponse("checkin.html", {"request": request, "equipo": None, "mensaje": None})


@router.post("/buscar")
def buscar_equipo(datos: schemas.CheckInBuscar, db: Session = Depends(get_db)):
    """
    Busca un equipo por nombre, código (NF-001) o por el contenido crudo
    del QR escaneado (formato 'EQUIPO:<id>:<codigo>').
    """
    termino = datos.termino.strip()

    # Si el QR fue escaneado, viene en formato EQUIPO:<id>:<codigo>
    if termino.upper().startswith("EQUIPO:"):
        partes = termino.split(":")
        if len(partes) >= 2 and partes[1].isdigit():
            equipo = crud.obtener_equipo(db, int(partes[1]))
            return _serializar_equipo_checkin(equipo)

    equipo = crud.obtener_equipo_por_codigo_o_nombre(db, termino)
    if not equipo:
        raise HTTPException(status_code=404, detail="No se encontró ningún equipo con ese nombre o código")

    return _serializar_equipo_checkin(equipo)


def _serializar_equipo_checkin(equipo: models.Equipo) -> dict:
    return {
        "id": equipo.id,
        "codigo": equipo.codigo,
        "nombre": equipo.nombre,
        "categoria": equipo.categoria.value if hasattr(equipo.categoria, "value") else equipo.categoria,
        "estado": equipo.estado.value if hasattr(equipo.estado, "value") else equipo.estado,
        "atletas": [a.nombre for a in equipo.atletas],
        "kit_entregado": bool(equipo.checkin and equipo.checkin.kit_entregado),
    }


@router.post("/registrar", response_model=schemas.CheckInOut)
def registrar_checkin(datos: schemas.CheckInRegistrar, db: Session = Depends(get_db)):
    """Registra la llegada del equipo y la entrega del kit."""
    return crud.registrar_checkin(
        db,
        equipo_id=datos.equipo_id,
        responsable=datos.responsable,
        kit_entregado=datos.kit_entregado,
    )


@router.get("/qr/{equipo_id}")
def obtener_qr(equipo_id: int, db: Session = Depends(get_db)):
    """(Re)genera y devuelve la ruta del QR de un equipo."""
    equipo = crud.obtener_equipo(db, equipo_id)
    ruta_qr = utils.generar_qr_equipo(equipo.id, equipo.codigo)
    return {"ruta_qr": ruta_qr}
