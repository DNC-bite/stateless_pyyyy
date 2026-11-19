import logging

from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .services import migrar_carrito_de_sesion

log = logging.getLogger(__name__)


@receiver(user_logged_in)
def unir_carrito_al_iniciar_sesion(sender, request, user, **kwargs):
    if request is None:
        return
    try:
        migrar_carrito_de_sesion(request, user)
    except Exception:  # noqa: BLE001  (nunca debe impedir que alguien inicie sesión)
        log.exception("No se pudo unir el carrito de invitado de %s", user)
