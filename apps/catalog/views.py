from django.shortcuts import get_object_or_404, render

from .models import Categoria, Producto


def coleccion(request, slug):
    categoria = get_object_or_404(Categoria, slug=slug, estado=True)
    productos = (
        Producto.objects.activos()
        .filter(categoria=categoria)
        .con_stock_total()
        .prefetch_related("variantes")
    )
    return render(
        request,
        "catalog/coleccion.html",
        {"categoria": categoria, "productos": productos},
    )


def producto_detalle(request, product_id):
    producto = get_object_or_404(
        Producto.objects.activos()
        .select_related("categoria")
        .prefetch_related("variantes"),
        pk=product_id,
    )
    return render(
        request,
        "catalog/producto.html",
        {
            "producto": producto,
            "tallas": producto.tallas,
            "variantes": producto.variantes.all(),
        },
    )
