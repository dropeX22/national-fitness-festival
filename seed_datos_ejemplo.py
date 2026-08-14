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
        "consentimiento_datos_aceptado": True,
        "atletas": [
            {"nombre": "Carlos", "apellido": "Pérez", "cedula": "8-111-1111", "fecha_nacimiento": "1995-03-14",
             "genero": "M", "nacionalidad": "Panameña", "talla": "L", "box": "CrossFit 507", "tipo_sangre": "O+",
             "email": "carlos@example.com", "email_confirmacion": "carlos@example.com", "telefono": "6000-1111", "es_capitan": True},
            {"nombre": "Luis", "apellido": "Gómez", "cedula": "8-222-2222", "fecha_nacimiento": "1993-07-22",
             "genero": "M", "nacionalidad": "Panameña", "talla": "M", "box": "CrossFit 507", "tipo_sangre": "A+",
             "es_capitan": False},
            {"nombre": "María", "apellido": "Rodríguez", "cedula": "8-333-3333", "fecha_nacimiento": "1997-11-02",
             "genero": "F", "nacionalidad": "Panameña", "talla": "S", "box": "CrossFit 507", "tipo_sangre": "B+",
             "es_capitan": False},
            {"nombre": "Ana", "apellido": "Torres", "cedula": "8-444-4444", "fecha_nacimiento": "1996-05-30",
             "genero": "F", "nacionalidad": "Panameña", "talla": "M", "box": "CrossFit 507", "tipo_sangre": "O-",
             "es_capitan": False},
        ],
    },
    {
        "nombre": "Fuerza Panameña",
        "categoria": "Principiante",
        "reglamento_aceptado": True,
        "consentimiento_datos_aceptado": True,
        "atletas": [
            {"nombre": "José", "apellido": "Ramírez", "cedula": "8-555-5555", "fecha_nacimiento": "1990-01-10",
             "genero": "M", "nacionalidad": "Panameña", "talla": "XL", "box": "Box Central", "tipo_sangre": "AB+",
             "email": "jose@example.com", "email_confirmacion": "jose@example.com", "telefono": "6000-2222", "es_capitan": True},
            {"nombre": "Pedro", "apellido": "Sánchez", "cedula": "8-666-6666", "fecha_nacimiento": "1994-09-18",
             "genero": "M", "nacionalidad": "Panameña", "talla": "L", "box": "Box Central", "tipo_sangre": "A-",
             "es_capitan": False},
            {"nombre": "Sofía", "apellido": "Castillo", "cedula": "8-777-7777", "fecha_nacimiento": "1998-02-25",
             "genero": "F", "nacionalidad": "Panameña", "talla": "S", "box": "Box Central", "tipo_sangre": "O+",
             "es_capitan": False},
            {"nombre": "Valeria", "apellido": "Ortega", "cedula": "8-888-8888", "fecha_nacimiento": "1999-12-05",
             "genero": "F", "nacionalidad": "Panameña", "talla": "M", "box": "Box Central", "tipo_sangre": "B-",
             "es_capitan": False},
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
