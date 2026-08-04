"""
abrir_nuevo_evento.py
----------------------
Ejecuta este script UNA VEZ, cuando quieras abrir las inscripciones del
año siguiente. Cierra el evento activo actual (queda como historial, con
sus equipos y atletas intactos) y crea uno nuevo que pasa a ser el activo.

A partir de ese momento:
- Las inscripciones nuevas se conectan automáticamente al evento nuevo.
- Un atleta que ya compitió el año pasado puede volver a inscribirse sin
  ningún problema (la restricción de cédula única es por evento, no global).

Uso (edita las variables de abajo con los datos del nuevo evento y corre):
    python abrir_nuevo_evento.py
"""

import datetime
from app.database import SessionLocal, init_db
from app import crud

# --- EDITA ESTOS VALORES ANTES DE CORRER EL SCRIPT ---
NOMBRE_NUEVO_EVENTO = "National Fitness Festival 2027"
FECHA_NUEVO_EVENTO = datetime.datetime(2027, 11, 14, 8, 0)
PRECIO_INSCRIPCION = 200.0
DESCRIPCION = "Competencia de CrossFit por equipos en Panamá — edición 2027."
# -------------------------------------------------------

init_db()
db = SessionLocal()

evento_anterior = crud.obtener_o_crear_evento(db)
print(f"Evento activo actual: {evento_anterior.nombre} (id={evento_anterior.id})")

confirmacion = input(
    f"\n¿Confirmas cerrar este evento y abrir '{NOMBRE_NUEVO_EVENTO}'? (escribe 'si' para continuar): "
)
if confirmacion.strip().lower() != "si":
    print("Cancelado. No se hizo ningún cambio.")
else:
    nuevo_evento = crud.crear_nuevo_evento_anual(
        db,
        nombre=NOMBRE_NUEVO_EVENTO,
        fecha=FECHA_NUEVO_EVENTO,
        precio=PRECIO_INSCRIPCION,
        descripcion=DESCRIPCION,
    )
    print(f"\n✅ Nuevo evento activo: {nuevo_evento.nombre} (id={nuevo_evento.id})")
    print(f"   El evento anterior (id={evento_anterior.id}) queda guardado como historial.")

db.close()
