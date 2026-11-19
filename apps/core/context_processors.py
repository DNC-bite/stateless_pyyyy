from django.conf import settings

from apps.cart.services import get_cart_count


def tienda(request):
    """Variables disponibles en todas las plantillas."""
    return {
        "empresa_nombre": settings.EMPRESA_NOMBRE,
        "google_habilitado": bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET),
        "cart_count": get_cart_count(request),
    }
