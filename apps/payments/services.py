"""Capa de integración con Mercado Pago Checkout Pro (Preferences API)."""

import logging
from decimal import Decimal, InvalidOperation

import mercadopago
from django.conf import settings
from django.db import transaction

from apps.orders.models import Venta

from .models import Payment

logger = logging.getLogger(__name__)


class MercadoPagoError(Exception):
    pass


def get_sdk():
    access_token = settings.MERCADOPAGO_ACCESS_TOKEN.strip()
    if not access_token or access_token == "PEGA_EL_TOKEN_NUEVO":
        raise MercadoPagoError(
            "Configura un Access Token real de Mercado Pago en el archivo .env."
        )
    return mercadopago.SDK(access_token)


def create_preference(payment):
    front = settings.BASE_URL.rstrip("/")
    public_url = settings.MERCADOPAGO_PUBLIC_URL.rstrip("/")
    preference_data = {
        "items": [
            {
                "id": str(payment.venta_id),
                "title": payment.title,
                "description": payment.description or payment.title,
                "quantity": payment.quantity,
                "unit_price": float(payment.unit_price),
                "currency_id": payment.currency_id,
            }
        ],
        "external_reference": str(payment.reference),
        "back_urls": {
            "success": f"{front}/account/pedidos/{payment.venta_id}?pago=exitoso",
            "failure": f"{front}/account/pedidos/{payment.venta_id}?pago=fallido",
            "pending": f"{front}/account/pedidos/{payment.venta_id}?pago=pendiente",
        },
        "notification_url": f"{public_url}/api/payments/webhook/",
    }
    if front.startswith("https://"):
        preference_data["auto_return"] = "approved"
    if payment.payer_email:
        preference_data["payer"] = {"email": payment.payer_email}

    result = get_sdk().preference().create(preference_data)
    if result.get("status") not in (200, 201):
        logger.error("Error creando preferencia de Mercado Pago: %s", result)
        raise MercadoPagoError(
            f"Mercado Pago respondió {result.get('status')}: {result.get('response')}"
        )

    response = result.get("response") or {}
    if not response.get("id"):
        raise MercadoPagoError("Mercado Pago no devolvió el identificador de la preferencia.")
    payment.preference_id = str(response["id"])
    payment.init_point = response.get("init_point", "")
    payment.sandbox_init_point = response.get("sandbox_init_point", "")
    payment.save(
        update_fields=["preference_id", "init_point", "sandbox_init_point", "updated_at"]
    )
    return payment


def create_payment_preference(venta):
    payment = Payment.objects.filter(venta=venta).first()
    if payment and payment.preference_id:
        return payment, False
    if payment is None:
        payment = Payment.objects.create(
            venta=venta,
            title=f"Pedido {venta.numero_factura}",
            description=f"Compra STATELESS {venta.numero_factura}",
            unit_price=venta.total,
            payer_email=venta.usuario.email,
        )
    else:
        payment.status = Payment.Status.PENDING
        payment.save(update_fields=["status", "updated_at"])

    try:
        create_preference(payment)
    except MercadoPagoError:
        logger.exception("Falló la creación de la preferencia")
        payment.status = Payment.Status.REJECTED
        payment.status_detail = "preference_creation_failed"
        payment.save(update_fields=["status", "status_detail", "updated_at"])
        raise

    venta.metodo_pago = Venta.Metodo.MERCADO_PAGO
    venta.save(update_fields=["metodo_pago", "updated_at"])
    return payment, True


def fetch_payment(mp_payment_id):
    result = get_sdk().payment().get(mp_payment_id)
    if result.get("status") != 200:
        raise MercadoPagoError(
            f"No se pudo consultar el pago {mp_payment_id}: {result.get('response')}"
        )
    return result["response"]


def sync_payment_from_mp(mp_payment_id):
    data = fetch_payment(mp_payment_id)
    reference = data.get("external_reference")
    if not reference:
        logger.warning("Pago de Mercado Pago %s sin external_reference", mp_payment_id)
        return None

    try:
        payment = Payment.objects.select_related("venta").get(reference=reference)
    except (Payment.DoesNotExist, ValueError):
        logger.warning("Pago %s con external_reference desconocida: %s", mp_payment_id, reference)
        return None

    try:
        amount = Decimal(str(data["transaction_amount"]))
    except (KeyError, InvalidOperation, TypeError):
        raise MercadoPagoError(f"El pago {mp_payment_id} no incluye un monto válido.")
    if amount != payment.total_amount or data.get("currency_id") != payment.currency_id:
        raise MercadoPagoError(
            f"El monto o la moneda del pago {mp_payment_id} no coincide con la venta."
        )

    new_status = data.get("status", payment.status)
    valid_statuses = {choice.value for choice in Payment.Status}
    payment.status = new_status if new_status in valid_statuses else payment.status
    payment.status_detail = data.get("status_detail") or ""
    payment.mp_payment_id = str(data.get("id", mp_payment_id))
    payment.payment_method = data.get("payment_method_id") or ""
    payment.raw_response = data

    with transaction.atomic():
        payment.save()
        if payment.status == Payment.Status.APPROVED:
            venta = Venta.objects.select_for_update().get(pk=payment.venta_id)
            if venta.estado == Venta.Estado.PENDIENTE_PAGO:
                venta.estado = Venta.Estado.PAGO_CONFIRMADO
                venta.metodo_pago = Venta.Metodo.MERCADO_PAGO
                venta.save(update_fields=["estado", "metodo_pago", "updated_at"])
    return payment
