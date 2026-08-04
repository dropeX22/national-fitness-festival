"""
database.py
------------
Configura la conexión a la base de datos SQLite usando SQLAlchemy.
Aquí se crea el "motor" (engine) de la base de datos y la fábrica de
sesiones (SessionLocal) que usaremos en cada request para hablar con la BD.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

# Cargamos las variables de entorno del archivo .env (si existe)
load_dotenv()

# URL de la base de datos. Por defecto usamos un archivo SQLite local.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./evento.db")

# Algunos proveedores (incluyendo Render en ciertos casos) entregan la URL
# de PostgreSQL con el prefijo antiguo "postgres://". Ambos prefijos
# apuntan al mismo protocolo, pero SQLAlchemy 2.x solo acepta el nombre
# moderno "postgresql://". Sin esta línea, conectar a una base de datos
# real de Render fallaría con un error de "dialect not found".
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# connect_args es necesario solo para SQLite (permite usarlo desde varios hilos,
# como hace FastAPI internamente).
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)

# SessionLocal es una "fábrica" de sesiones. Cada request abrirá su propia sesión.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base es la clase de la que heredarán todos nuestros modelos (tablas).
Base = declarative_base()


def get_db():
    """
    Dependencia de FastAPI: abre una sesión de BD, la entrega a la ruta
    que la solicite, y se asegura de cerrarla al final (incluso si hay error).
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Crea todas las tablas en la base de datos según los modelos definidos
    en models.py. Se debe llamar una sola vez al iniciar el proyecto.
    """
    # Importamos los modelos aquí (no arriba) para evitar problemas de
    # importación circular entre database.py y models.py
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    print("✅ Base de datos creada/verificada correctamente (evento.db)")
