from django.conf import settings

from apps.cart.services import cantidad_en_bolsa


def tienda(request):
    """Variables disponibles en todas las plantillas."""
    return {
        "empresa_nombre": settings.EMPRESA_NOMBRE,
        "google_habilitado": bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET),
        "cart_count": cantidad_en_bolsa(request),
        "modo_demo_pagos": settings.MODO_DEMO_PAGOS,
        "empresa_correo_soporte": settings.EMPRESA_CORREO_SOPORTE,
    }
