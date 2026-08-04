"""
run.py
------
Script simple para arrancar el servidor sin tener que recordar el
comando completo de uvicorn. Ejecuta: python run.py
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
