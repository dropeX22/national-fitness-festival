"""
utils.py
--------
Funciones auxiliares: generación de códigos QR y envío de correos.
Estas funciones NO dependen de FastAPI, así se pueden probar por separado.
"""

import os
import base64
import qrcode
import requests

# Carpeta donde se guardan las imágenes QR generadas
CARPETA_QR = os.path.join(os.path.dirname(__file__), "static", "qrcodes")
os.makedirs(CARPETA_QR, exist_ok=True)


def generar_qr_equipo(equipo_id: int, codigo_equipo: str) -> str:
    """
    Genera una imagen QR que contiene el ID y código del equipo.
    El día del evento, el check-in escanea este QR para identificar
    rápidamente al equipo. Devuelve la ruta relativa del archivo generado.
    """
    contenido = f"EQUIPO:{equipo_id}:{codigo_equipo}"
    img = qrcode.make(contenido)

    nombre_archivo = f"{codigo_equipo}.png"
    ruta_completa = os.path.join(CARPETA_QR, nombre_archivo)
    img.save(ruta_completa)

    # Ruta relativa para usar en templates con /static/...
    return f"/static/qrcodes/{nombre_archivo}"


def enviar_correo_confirmacion(destinatario: str, nombre_equipo: str, codigo_equipo: str, ruta_qr_local: str):
    """
    Envía el correo de confirmación usando la API HTTP de Brevo (antes
    Sendinblue), en vez de SMTP tradicional. Esto es necesario porque
    Render bloquea los puertos SMTP (25, 465, 587) en su plan gratuito,
    pero SÍ permite tráfico HTTPS normal (puerto 443), que es lo que usa
    esta API.
    """
    api_key = os.getenv("BREVO_API_KEY")
    remitente = os.getenv("EMAIL_REMITENTE")

    asunto = f"Inscripción confirmada - National Fitness Festival ({codigo_equipo})"
    cuerpo_html = f"""
        <p>Hola,</p>
        <p>El equipo <b>{nombre_equipo}</b> (código {codigo_equipo}) ha sido registrado
        para el National Fitness Festival.</p>
        <p>Adjuntamos el código QR que deberán presentar el día del evento
        para hacer el check-in y recibir su kit.</p>
        <p><b>Instrucciones para el día del evento:</b></p>
        <ol>
          <li>Llegar con al menos 30 minutos de anticipación.</li>
          <li>Presentar el QR (impreso o en el celular).</li>
          <li>Todos los integrantes del equipo deben estar presentes.</li>
        </ol>
        <p>¡Nos vemos en la competencia!<br>Equipo organizador - National Fitness Festival</p>
    """

    if not api_key or not remitente:
        print("⚠️  Envío de correo SIMULADO (configura BREVO_API_KEY y EMAIL_REMITENTE en .env)")
        print(f"    Para: {destinatario}")
        print(f"    Asunto: {asunto}")
        return False

    payload = {
        "sender": {"email": remitente, "name": "National Fitness Festival"},
        "to": [{"email": destinatario}],
        "subject": asunto,
        "htmlContent": cuerpo_html,
    }

    # Adjuntamos el QR si existe, codificado en base64 (así lo pide la API)
    if ruta_qr_local and os.path.exists(ruta_qr_local):
        with open(ruta_qr_local, "rb") as archivo:
            contenido_base64 = base64.b64encode(archivo.read()).decode("utf-8")
        payload["attachment"] = [{"content": contenido_base64, "name": f"{codigo_equipo}.png"}]

    try:
        respuesta = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            json=payload,
            headers={"api-key": api_key, "Content-Type": "application/json"},
            timeout=10,
        )
        respuesta.raise_for_status()
        return True
    except Exception as error:
        print(f"❌ Error enviando correo: {error}")
        return False