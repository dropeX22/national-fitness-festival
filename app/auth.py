"""
auth.py
-------
Autenticación HTTP Basic para proteger el panel de administración y el
check-in. Es el mecanismo más simple que existe: el navegador muestra un
cuadro nativo de usuario/contraseña, y nosotros solo verificamos que
coincidan con lo que configuramos en el archivo .env.

IMPORTANTE: HTTP Basic manda las credenciales en cada petición. Es seguro
SOLO si el sitio usa HTTPS (Render y Railway lo dan gratis). Nunca lo uses
sobre HTTP plano en producción.
"""

import os
import secrets
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

seguridad = HTTPBasic()

# Usuario y contraseña del staff, definidos en el .env (nunca en el código)
ADMIN_USUARIO = os.getenv("ADMIN_USUARIO", "admin")
ADMIN_CLAVE = os.getenv("ADMIN_CLAVE", "changeme")


def verificar_credenciales(credenciales: HTTPBasicCredentials = Depends(seguridad)):
    """
    Dependencia de FastAPI que se ejecuta ANTES de entrar a cualquier ruta
    que la use. Si las credenciales no coinciden, corta la petición con
    un error 401 y el navegador vuelve a pedir usuario/contraseña.

    Usamos secrets.compare_digest() en vez de simplemente "==" porque una
    comparación normal de strings puede tardar un poquito más o menos
    dependiendo de en qué letra falla (un "timing attack"). compare_digest
    siempre tarda lo mismo, sin importar en qué carácter esté el error,
    así que no filtra información sobre qué tan "cerca" estuvo el intento.
    """
    usuario_correcto = secrets.compare_digest(credenciales.username, ADMIN_USUARIO)
    clave_correcta = secrets.compare_digest(credenciales.password, ADMIN_CLAVE)

    if not (usuario_correcto and clave_correcta):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Basic"},  # esto le dice al navegador que muestre el cuadro de login
        )
    return credenciales.username
