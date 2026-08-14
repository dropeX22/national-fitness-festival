"""
routes/payments.py
-------------------
Integración con Yappy (Banco General, Panamá).

IMPORTANTE PARA EL ESTUDIANTE:
Yappy Comercial ofrece un "botón de pago" que redirige al usuario a la app
de Yappy para pagar. La integración real requiere:
  1. Una cuenta comercial en Yappy y credenciales (merchant id / secret).
  2. Llamar a su API para generar la orden de pago (obtienes una URL o un
     "hash" de pago que se usa para el botón).
  3. Yappy notifica el resultado a un webhook que tú expones.

Como el estudiante probablemente NO tiene credenciales reales todavía,
este archivo incluye:
  - Un modo REAL (comentado/aislado) que se activa si hay credenciales en .env.
  - Un modo SIMULADO que permite probar todo el flujo sin dinero real.
"""

import os
import requests
from fastapi import APIRouter, Depends, HTTPException, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app import crud, schemas, models, utils

router = APIRouter(tags=["Pagos"])

YAPPY_MERCHANT_ID = os.getenv("YAPPY_MERCHANT_ID")
YAPPY_SECRET_KEY = os.getenv("YAPPY_SECRET_KEY")
YAPPY_API_URL = os.getenv("YAPPY_API_URL", "https://apipagosbg.bgeneral.com")  # URL de ejemplo, verificar en docs oficiales
MODO_SIMULADO = not (YAPPY_MERCHANT_ID and YAPPY_SECRET_KEY)


def _avisar_organizacion(equipo: models.Equipo, metodo_pago: str):
    """Dispara el correo interno de aviso, tal como se definió: al momento de elegir método de pago."""
    capitan = equipo.capitan
    utils.enviar_correo_aviso_organizacion(
        nombre_equipo=equipo.nombre,
        codigo_equipo=equipo.codigo,
        metodo_pago=metodo_pago,
        capitan_nombre=f"{capitan.nombre} {capitan.apellido}" if capitan else "N/D",
        capitan_email=capitan.email if capitan else "N/D",
        capitan_telefono=capitan.telefono if capitan else "N/D",
    )


@router.post("/pago/{equipo_id}/yappy")
def generar_pago_yappy(equipo_id: int, db: Session = Depends(get_db), telefono_yappy: str = Form(...)):
    """
    Crea el pago con método Yappy y devuelve la URL a la que el capitán
    debe ir para pagar (botón de Yappy real o simulado). El teléfono de
    Yappy es aparte del teléfono del capitán, porque a veces usan el
    Yappy de alguien externo al equipo.
    """
    equipo = crud.obtener_equipo(db, equipo_id)
    evento = crud.obtener_o_crear_evento(db)

    pago = crud.crear_pago(db, equipo_id, evento.precio_inscripcion, models.MetodoPagoEnum.yappy, telefono_yappy)
    _avisar_organizacion(equipo, "Yappy")

    if MODO_SIMULADO:
        # En modo simulado, en vez de ir a Yappy real, mandamos al usuario
        # a nuestra propia página de "pago simulado" para poder probar el flujo.
        url_pago = f"/pago/simular/{pago.referencia_yappy}"
    else:
        url_pago = _crear_orden_yappy_real(pago, equipo)

    return {
        "referencia_yappy": pago.referencia_yappy,
        "monto": pago.monto,
        "url_pago": url_pago,
        "modo_simulado": MODO_SIMULADO,
    }


@router.post("/pago/{equipo_id}/transferencia")
def generar_pago_transferencia(equipo_id: int, db: Session = Depends(get_db)):
    """
    Crea el pago con método Transferencia: queda "Pendiente de
    verificación" con un plazo, manda el correo 1 al capitán (avisando
    del plazo) y el correo interno a la organización para que revisen
    el estado de cuenta del banco.
    """
    equipo = crud.obtener_equipo(db, equipo_id)
    evento = crud.obtener_o_crear_evento(db)

    pago = crud.crear_pago(db, equipo_id, evento.precio_inscripcion, models.MetodoPagoEnum.transferencia)

    capitan = equipo.capitan
    if capitan and capitan.email:
        utils.enviar_correo_transferencia_pendiente(
            destinatario=capitan.email,
            nombre_equipo=equipo.nombre,
            codigo_equipo=equipo.codigo,
            horas_plazo=crud.HORAS_PLAZO_VERIFICACION_TRANSFERENCIA,
        )
    _avisar_organizacion(equipo, "Transferencia")

    return RedirectResponse(url=f"/confirmacion/{equipo_id}", status_code=303)


def _crear_orden_yappy_real(pago: models.Pago, equipo: models.Equipo) -> str:
    """
    Llama a la API real de Yappy Comercial para generar la orden de pago.
    NOTA: los nombres de endpoint/campos son ilustrativos; el estudiante debe
    ajustar esto con la documentación oficial que Yappy entrega al comercio.
    """
    try:
        respuesta = requests.post(
            f"{YAPPY_API_URL}/payments/create",
            json={
                "merchantId": YAPPY_MERCHANT_ID,
                "orderId": pago.referencia_yappy,
                "amount": pago.monto,
                "description": f"Inscripción {equipo.codigo} - National Fitness Festival",
                "webhookUrl": os.getenv("YAPPY_WEBHOOK_URL", "http://localhost:8000/webhook/yappy"),
            },
            headers={"Authorization": f"Bearer {YAPPY_SECRET_KEY}"},
            timeout=10,
        )
        respuesta.raise_for_status()
        return respuesta.json()["payment_url"]
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"Error comunicándose con Yappy: {error}")


# ---------------------------------------------------------------------------
# MODO SIMULADO: página/endpoint para "pagar" sin dinero real (pruebas)
# ---------------------------------------------------------------------------

@router.get("/pago/simular/{referencia}")
def pagina_pago_simulado(referencia: str):
    """
    Devuelve un HTML muy simple que simula la pantalla de Yappy, con un
    botón para 'Confirmar pago' o 'Rechazar pago'. Solo para desarrollo.
    """
    from fastapi.responses import HTMLResponse

    html = f"""
    <html>
    <head><title>Simulación de pago Yappy</title>
    <link rel="stylesheet" href="/static/style.css"></head>
    <body>
      <div style="max-width:420px;margin:60px auto;text-align:center;font-family:sans-serif;">
        <h2>💳 Simulación de pago Yappy</h2>
        <p>Referencia: <b>{referencia}</b></p>
        <p>Este es un entorno de PRUEBA. No se procesa dinero real.</p>
        <form action="/pago/simular/{referencia}/confirmar" method="post" style="margin-top:20px;">
          <button type="submit" style="background:#00b894;color:white;border:none;padding:12px 24px;border-radius:8px;font-size:16px;cursor:pointer;">
            ✅ Confirmar pago
          </button>
        </form>
        <form action="/pago/simular/{referencia}/rechazar" method="post" style="margin-top:10px;">
          <button type="submit" style="background:#d63031;color:white;border:none;padding:12px 24px;border-radius:8px;font-size:16px;cursor:pointer;">
            ❌ Rechazar pago
          </button>
        </form>
      </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@router.post("/pago/simular/{referencia}/confirmar")
def confirmar_pago_simulado(referencia: str, db: Session = Depends(get_db)):
    """Simula que Yappy confirmó el pago (dispara la misma lógica del webhook real)."""
    pago = db.query(models.Pago).filter(models.Pago.referencia_yappy == referencia).first()
    if not pago:
        raise HTTPException(status_code=404, detail="Referencia no encontrada")

    crud.confirmar_pago_por_referencia(
        db, referencia_yappy=referencia, estado_nuevo=models.EstadoPagoEnum.confirmado, monto=pago.monto
    )
    return RedirectResponse(url=f"/confirmacion/{pago.equipo_id}", status_code=303)


@router.post("/pago/simular/{referencia}/rechazar")
def rechazar_pago_simulado(referencia: str, db: Session = Depends(get_db)):
    pago = db.query(models.Pago).filter(models.Pago.referencia_yappy == referencia).first()
    if not pago:
        raise HTTPException(status_code=404, detail="Referencia no encontrada")

    crud.confirmar_pago_por_referencia(
        db, referencia_yappy=referencia, estado_nuevo=models.EstadoPagoEnum.rechazado, monto=pago.monto
    )
    return RedirectResponse(url=f"/confirmacion/{pago.equipo_id}", status_code=303)


# ---------------------------------------------------------------------------
# WEBHOOK REAL DE YAPPY
# ---------------------------------------------------------------------------

@router.post("/webhook/yappy")
def webhook_yappy(payload: schemas.WebhookYappyPayload, db: Session = Depends(get_db)):
    """
    Endpoint que Yappy llamará automáticamente cuando el estado de un pago
    cambie (confirmado/rechazado). Debes registrar esta URL pública en el
    panel de Yappy Comercial (por ejemplo: https://tu-dominio.com/webhook/yappy).

    Manejo de pagos duplicados: si Yappy reenvía la misma notificación,
    confirmar_pago_por_referencia detecta que ya estaba confirmado y no
    vuelve a duplicar nada.
    """
    estado_normalizado = (
        models.EstadoPagoEnum.confirmado
        if payload.estado.lower() in ("confirmado", "approved", "success")
        else models.EstadoPagoEnum.rechazado
    )

    pago = crud.confirmar_pago_por_referencia(
        db,
        referencia_yappy=payload.referencia_yappy,
        estado_nuevo=estado_normalizado,
        monto=payload.monto,
    )
    return {"ok": True, "pago_id": pago.id, "estado": pago.estado}
