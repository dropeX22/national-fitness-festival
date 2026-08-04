"""
utils.py
--------
Funciones auxiliares: generación de códigos QR y envío de correos.
Estas funciones NO dependen de FastAPI, así se pueden probar por separado.
"""

import os
import qrcode

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
    Envía un correo al capitán con los detalles de la inscripción y el QR
    adjunto. Usa yagmail, que requiere las variables de entorno:
      EMAIL_REMITENTE y EMAIL_CLAVE_APP (contraseña de aplicación de Gmail).

    Si esas variables no están configuradas (por ejemplo en desarrollo),
    la función simplemente imprime un mensaje en consola en vez de fallar,
    para que el resto del sistema siga funcionando sin correo real.
    """
    remitente = os.getenv("EMAIL_REMITENTE")
    clave = os.getenv("EMAIL_CLAVE_APP")

    asunto = f"Inscripción confirmada - National Fitness Festival ({codigo_equipo})"
    cuerpo = (
        f"Hola,\n\n"
        f"El equipo '{nombre_equipo}' (código {codigo_equipo}) ha sido registrado "
        f"para el National Fitness Festival.\n\n"
        f"Adjuntamos el código QR que deberán presentar el día del evento "
        f"para hacer el check-in y recibir su kit.\n\n"
        f"Instrucciones para el día del evento:\n"
        f"1. Llegar con al menos 30 minutos de anticipación.\n"
        f"2. Presentar el QR (impreso o en el celular).\n"
        f"3. Todos los integrantes del equipo deben estar presentes.\n\n"
        f"¡Nos vemos en la competencia!\n"
        f"Equipo organizador - National Fitness Festival"
    )

    if not remitente or not clave:
        # Modo simulado: no hay credenciales configuradas
        print("⚠️  Envío de correo SIMULADO (configura EMAIL_REMITENTE y EMAIL_CLAVE_APP en .env)")
        print(f"    Para: {destinatario}")
        print(f"    Asunto: {asunto}")
        return False

    try:
        import yagmail
        yag = yagmail.SMTP(remitente, clave)
        yag.send(
            to=destinatario,
            subject=asunto,
            contents=cuerpo,
            attachments=[ruta_qr_local] if ruta_qr_local and os.path.exists(ruta_qr_local) else None,
        )
        return True
    except Exception as error:
        # No queremos que un error de correo tumbe la inscripción del equipo
        print(f"❌ Error enviando correo: {error}")
        return False
