"""
utils.py
--------
Funciones auxiliares: generación de códigos QR y envío de correos.
Estas funciones NO dependen de FastAPI, así se pueden probar por separado.

NOTA SOBRE EL CORREO: usamos la API HTTP de Brevo (antes Sendinblue), NO
SMTP tradicional (yagmail/smtplib). Esto es necesario porque Render
bloquea los puertos SMTP (25, 465, 587) en su plan gratuito, pero SÍ
permite tráfico HTTPS normal (puerto 443), que es lo que usa esta API.
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


def _enviar_email_brevo(destinatario: str, asunto: str, cuerpo_html: str, ruta_adjunto: str | None = None, nombre_adjunto: str | None = None) -> bool:
    """
    Función genérica que envía cualquier correo a través de la API de
    Brevo. Todas las funciones de correo específicas (confirmación,
    aviso interno, transferencia pendiente/confirmada) usan esta por
    debajo, para no repetir la misma lógica de conexión 4 veces.

    Si no hay credenciales configuradas (BREVO_API_KEY, EMAIL_REMITENTE),
    simula el envío imprimiendo en consola — así el resto del sistema
    sigue funcionando sin correo real configurado (ej. en desarrollo local).
    """
    api_key = os.getenv("BREVO_API_KEY")
    remitente = os.getenv("EMAIL_REMITENTE")

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

    if ruta_adjunto and os.path.exists(ruta_adjunto):
        with open(ruta_adjunto, "rb") as archivo:
            contenido_base64 = base64.b64encode(archivo.read()).decode("utf-8")
        payload["attachment"] = [{"content": contenido_base64, "name": nombre_adjunto or "adjunto.png"}]

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
        # No queremos que un error de correo tumbe ninguna operación del sistema
        print(f"❌ Error enviando correo: {error}")
        return False


def enviar_correo_confirmacion(destinatario: str, nombre_equipo: str, codigo_equipo: str, ruta_qr_local: str) -> bool:
    """Correo al capitán apenas se inscribe el equipo, con el QR adjunto."""
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
    return _enviar_email_brevo(destinatario, asunto, cuerpo_html, ruta_qr_local, f"{codigo_equipo}.png")


def enviar_correo_transferencia_pendiente(destinatario: str, nombre_equipo: str, codigo_equipo: str, horas_plazo: int) -> bool:
    """
    Correo 1 del flujo de transferencia: se envía apenas el capitán elige
    pagar por transferencia, indicando el plazo que tiene el staff para
    verificarla.
    """
    asunto = f"Recibimos tu transferencia - National Fitness Festival ({codigo_equipo})"
    cuerpo_html = f"""
        <p>Hola,</p>
        <p>Registramos que el equipo <b>{nombre_equipo}</b> (código {codigo_equipo})
        eligió pagar por <b>transferencia bancaria</b>.</p>
        <p>Nuestro equipo va a verificar manualmente que la transferencia haya
        llegado correctamente. Este proceso puede tardar hasta
        <b>{horas_plazo} horas</b>.</p>
        <p>Te enviaremos un segundo correo de confirmación en cuanto
        verifiquemos el pago y tu inscripción quede oficialmente confirmada.</p>
        <p>Si tienes dudas mientras tanto, puedes responder a este correo.</p>
        <p>Equipo organizador - National Fitness Festival</p>
    """
    return _enviar_email_brevo(destinatario, asunto, cuerpo_html)


def enviar_correo_transferencia_confirmada(destinatario: str, nombre_equipo: str, codigo_equipo: str) -> bool:
    """
    Correo 2 del flujo de transferencia: se envía cuando el staff verifica
    manualmente la transferencia desde el panel admin y marca el pago
    como confirmado.
    """
    asunto = f"¡Pago confirmado! - National Fitness Festival ({codigo_equipo})"
    cuerpo_html = f"""
        <p>Hola,</p>
        <p>Verificamos la transferencia del equipo <b>{nombre_equipo}</b> (código {codigo_equipo})
        y tu inscripción ya está <b>oficialmente confirmada</b>.</p>
        <p>Recuerda presentar el código QR que te enviamos en el correo de
        inscripción el día del evento, para hacer el check-in y recibir tu kit.</p>
        <p>¡Nos vemos en la competencia!<br>Equipo organizador - National Fitness Festival</p>
    """
    return _enviar_email_brevo(destinatario, asunto, cuerpo_html)


def enviar_correo_aviso_organizacion(nombre_equipo: str, codigo_equipo: str, metodo_pago: str, capitan_nombre: str, capitan_email: str, capitan_telefono: str) -> bool:
    """
    Correo INTERNO para el equipo organizador (no para el participante),
    avisando que un equipo eligió método de pago y qué deben verificar:
    - Si es transferencia: revisar el estado de cuenta del banco.
    - Si es Yappy: revisar que la solicitud de Yappy sí se haya completado.

    Se manda al correo definido en ADMIN_NOTIFICACION_EMAIL (.env). Si no
    está configurado, se simula igual que los demás correos.
    """
    destinatario = os.getenv("ADMIN_NOTIFICACION_EMAIL")
    if not destinatario:
        print("⚠️  ADMIN_NOTIFICACION_EMAIL no configurado — no se puede mandar el aviso interno")
        return False

    accion = (
        "Verifica el estado de cuenta del banco para confirmar la transferencia."
        if metodo_pago == "Transferencia"
        else "Verifica que la solicitud de Yappy se haya completado correctamente."
    )

    asunto = f"Nueva inscripción - {codigo_equipo} eligió pagar por {metodo_pago}"
    cuerpo_html = f"""
        <p>Se inscribió un equipo nuevo y ya eligió su método de pago:</p>
        <ul>
          <li><b>Equipo:</b> {nombre_equipo} ({codigo_equipo})</li>
          <li><b>Método de pago:</b> {metodo_pago}</li>
          <li><b>Capitán:</b> {capitan_nombre}</li>
          <li><b>Email del capitán:</b> {capitan_email}</li>
          <li><b>Teléfono del capitán:</b> {capitan_telefono}</li>
        </ul>
        <p>{accion}</p>
        <p>Puedes gestionar este equipo desde el panel de administración.</p>
    """
    return _enviar_email_brevo(destinatario, asunto, cuerpo_html)
