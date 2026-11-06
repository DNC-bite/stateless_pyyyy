from django.conf import settings


def tienda(request):
    """Variables disponibles en todas las plantillas."""
    return {
        "empresa_nombre": settings.EMPRESA_NOMBRE,
        "google_habilitado": bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET),
    }
