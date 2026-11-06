from decimal import Decimal

from django import template

from apps.core.utils import a_decimal, imagen_url as _imagen_url

register = template.Library()


@register.filter
def cop(valor, estilo="coma"):
    """
    Dinero en pesos sin decimales.
      {{ x|cop }}        -> 250,000   (tienda, carrito, listas)
      {{ x|cop:"punto" }} -> 250.000  (dashboard)
    """
    numero = a_decimal(valor).quantize(Decimal("1"))
    texto = f"{numero:,}"
    return texto.replace(",", ".") if estilo == "punto" else texto


@register.filter
def imagen_url(valor):
    return _imagen_url(valor)
