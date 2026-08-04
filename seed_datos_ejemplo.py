"""
seed_datos_ejemplo.py
----------------------
Crea 2 equipos de ejemplo en la base de datos para poder probar el
sistema (admin, check-in, pagos) sin tener que llenar el formulario
manualmente cada vez.

Uso:
    python seed_datos_ejemplo.py
"""

from app.database import SessionLocal, init_db
from app import crud, schemas, models

init_db()
db = SessionLocal()

equipos_ejemplo = [
    {
        "nombre": "Los Guerreros del Hierro",
        "categoria": "Avanzado",
        "reglamento_aceptado": True,
        "atletas": [
            {"nombre": "Carlos Pérez", "cedula": "8-111-1111", "email": "carlos@example.com", "genero": "M", "es_capitan": True},
            {"nombre": "Luis Gómez", "cedula": "8-222-2222", "email": "luis@example.com", "genero": "M", "es_capitan": False},
            {"nombre": "María Rodríguez", "cedula": "8-333-3333", "email": "maria@example.com", "genero": "F", "es_capitan": False},
            {"nombre": "Ana Torres", "cedula": "8-444-4444", "email": "ana@example.com", "genero": "F", "es_capitan": False},
        ],
    },
    {
        "nombre": "Fuerza Panameña",
        "categoria": "Principiante",
        "reglamento_aceptado": True,
        "atletas": [
            {"nombre": "José Ramírez", "cedula": "8-555-5555", "email": "jose@example.com", "genero": "M", "es_capitan": True},
            {"nombre": "Pedro Sánchez", "cedula": "8-666-6666", "email": "pedro@example.com", "genero": "M", "es_capitan": False},
            {"nombre": "Sofía Castillo", "cedula": "8-777-7777", "email": "sofia@example.com", "genero": "F", "es_capitan": False},
            {"nombre": "Valeria Ortega", "cedula": "8-888-8888", "email": "valeria@example.com", "genero": "F", "es_capitan": False},
        ],
    },
]

for datos_equipo in equipos_ejemplo:
    ya_existe = db.query(models.Equipo).filter(models.Equipo.nombre == datos_equipo["nombre"]).first()
    if ya_existe:
        print(f"⚠️  El equipo '{datos_equipo['nombre']}' ya existe, se omite.")
        continue

    esquema = schemas.EquipoCreate(**datos_equipo)
    equipo = crud.crear_equipo(db, esquema)
    print(f"✅ Equipo creado: {equipo.codigo} - {equipo.nombre}")

db.close()
print("\n🎉 Datos de ejemplo listos. Ejecuta 'python run.py' y visita http://localhost:8000/admin")
