"""
main.py
-------
Punto de entrada de la aplicación FastAPI. Aquí se:
  - crea la instancia de FastAPI
  - monta los archivos estáticos (CSS, JS, QR)
  - incluye todas las rutas (public, admin, payments, checkin)
  - crea la base de datos automáticamente al iniciar (si no existe)
"""

import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import init_db
from app.routes import public, admin, payments, checkin

app = FastAPI(
    title="National Fitness Festival - Sistema de Inscripciones",
    description="Sistema de inscripciones, pagos (Yappy) y check-in para el evento de CrossFit por equipos.",
    version="1.0.0",
)

# Carpeta de archivos estáticos (CSS, JS, imágenes QR)
CARPETA_ACTUAL = os.path.dirname(__file__)
app.mount("/static", StaticFiles(directory=os.path.join(CARPETA_ACTUAL, "static")), name="static")

# Registramos todas las rutas de la aplicación
app.include_router(public.router)
app.include_router(admin.router)
app.include_router(payments.router)
app.include_router(checkin.router)


@app.on_event("startup")
def al_iniciar():
    """Se ejecuta una sola vez cuando el servidor arranca."""
    init_db()
