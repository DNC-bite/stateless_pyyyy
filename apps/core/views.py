from django.shortcuts import render

from apps.catalog.models import Producto


def home(request):
    productos = (
        Producto.objects.activos()
        .con_stock_total()
        .select_related("categoria")
        .prefetch_related("variantes")[:8]
    )
    return render(request, "home.html", {"productos": productos})
