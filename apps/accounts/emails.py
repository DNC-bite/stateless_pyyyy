import logging

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from apps.core.mail import enviar_correo

log = logging.getLogger(__name__)


def _absoluta(ruta: str) -> str:
    return f"{settings.BASE_URL}{ruta}"


def enviar_verificacion(user, destino: str | None = None) -> bool:
    """Envía el enlace de verificación. Devuelve False (sin romper el flujo) si el correo falla."""
    destino = destino or user.email
    try:
        enviar_correo(
            destino,
            "✅ Verifica tu cuenta - STATELESS",
            "verificar_email",
            {"nombre": user.name, "url": _absoluta(reverse("verificar_email", args=[user.email_token])),
             "horas": settings.EMAIL_VERIFICATION_HOURS},
        )
        return True
    except Exception:  # noqa: BLE001  (el detalle va al registro del servidor, no al usuario)
        log.exception("No se pudo enviar el correo de verificación a %s", destino)
        return False


def enviar_recuperacion(user) -> bool:
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    try:
        enviar_correo(
            user.email,
            "🔑 Recupera tu contraseña - STATELESS",
            "recuperar_password",
            {"nombre": user.name, "url": _absoluta(reverse("restablecer_clave", args=[uid, token])),
             "minutos": settings.PASSWORD_RESET_TIMEOUT // 60},
        )
        return True
    except Exception:  # noqa: BLE001
        log.exception("No se pudo enviar el correo de recuperación a %s", user.email)
        return False
