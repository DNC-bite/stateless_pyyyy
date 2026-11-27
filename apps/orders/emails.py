import logging

from django.conf import settings
from django.urls import reverse

from apps.core.mail import enviar_correo

log = logging.getLogger(__name__)


def enviar_confirmacion_compra(venta) -> bool:
    """Nunca rompe la compra: si el correo falla, solo queda en el registro del servidor."""
    try:
        enviar_correo(
            venta.usuario.email,
            f"✅ Pedido #{venta.id} recibido - STATELESS",
            "compra_confirmada",
            {
                "venta": venta,
                "nombre": venta.usuario.name or "Cliente",
                "metodo": venta.get_metodo_pago_display(),
                "pagado": venta.estado != venta.Estado.PENDIENTE_PAGO,
                "seguimiento_url": f"{settings.BASE_URL}/account/tracking/{venta.id}",
            },
        )
        return True
    except Exception:  # noqa: BLE001
        log.exception("No se pudo enviar la confirmación del pedido #%s", venta.id)
        return False


ESTADO_LEGIBLE = {
    "preparando": "EN BODEGA / PREPARACIÓN",
    "en_curso": "EN CAMINO A TU DOMICILIO",
    "entregado": "ENTREGADO EN DESTINO",
}


def enviar_actualizacion_logistica(venta) -> bool:
    """Avisa al cliente de un movimiento de su envío. Nunca rompe el cambio de estado."""
    envio = venta.envio
    try:
        enviar_correo(
            venta.usuario.email,
            f"📦 Estado de tu Orden #{venta.id} - {ESTADO_LEGIBLE.get(envio.estado, envio.estado.upper())} | STATELESS",
            "logistica",
            {
                "venta": venta,
                "estado_legible": ESTADO_LEGIBLE.get(envio.estado, envio.estado.upper()),
                "transportadora": envio.get_transportadora_display() or "Por asignar",
                "guia": envio.numero_guia or "PENDIENTE DE ASIGNACIÓN",
                "seguimiento_url": f"{settings.BASE_URL}/account/tracking/{venta.id}",
            },
        )
        return True
    except Exception:  # noqa: BLE001
        log.exception("No se pudo enviar el aviso logístico del pedido #%s", venta.id)
        return False
