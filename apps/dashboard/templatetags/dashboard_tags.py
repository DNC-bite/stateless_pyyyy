from decimal import Decimal

from django import template

register = template.Library()


@register.filter
def cop(value):
    try:
        amount = Decimal(value or 0)
    except (TypeError, ValueError):
        return value
    return f"${amount:,.0f}".replace(",", ".")
