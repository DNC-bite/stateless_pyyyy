"""Funciones compartidas: imágenes, dinero e IVA."""
import unicodedata
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.templatetags.static import static

PLACEHOLDER = "images/placeholder.svg"


def imagen_url(valor: str) -> str:
    """
    Convierte lo guardado en la base de datos en una URL usable:
      - 'https://...'            -> se usa tal cual (Cloudinary)
      - '/images/x.png' o '/x'   -> ruta absoluta, tal cual
      - 'x.png'                  -> static/images/x.png
      - vacío                    -> imagen de respaldo propia
    """
    valor = (valor or "").strip()
    if not valor:
        return static(PLACEHOLDER)
    if valor.startswith(("http://", "https://", "/")):
        return valor
    return static(f"images/{valor}")


def sin_acentos(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto or "") if unicodedata.category(c) != "Mn"
    ).lower()


def a_decimal(valor) -> Decimal:
    return valor if isinstance(valor, Decimal) else Decimal(str(valor or 0))


def desglose_iva(total):
    """
    Los precios ya incluyen IVA: base = total / 1.19 (redondeo mitad hacia arriba, sin decimales).
    Devuelve (base, iva). Es la ÚNICA función de cálculo: pantalla, PDF, Excel y reportes la usan.
    """
    total = a_decimal(total)
    divisor = Decimal(100 + settings.IVA_PORCENTAJE) / Decimal(100)
    base = (total / divisor).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return base, total - base
