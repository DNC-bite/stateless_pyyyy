from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


def destinatario_real(correo: str) -> str:
    """
    Solo en desarrollo: si EMAIL_REDIRECT_TO está definido, los correos dirigidos a direcciones
    de prueba (@example.com) llegan a ese buzón. En producción nunca se desvía nada.
    """
    if settings.EMAIL_REDIRECT_TO and correo.lower().endswith("@example.com"):
        return settings.EMAIL_REDIRECT_TO
    return correo


def enviar_correo(destino: str, asunto: str, plantilla: str, contexto: dict) -> None:
    """Envía un correo con versión HTML (emails/<plantilla>.html) y texto (emails/<plantilla>.txt)."""
    texto = render_to_string(f"emails/{plantilla}.txt", contexto)
    html = render_to_string(f"emails/{plantilla}.html", contexto)
    msg = EmailMultiAlternatives(asunto, texto, settings.DEFAULT_FROM_EMAIL, [destinatario_real(destino)])
    msg.attach_alternative(html, "text/html")
    msg.send(fail_silently=False)
