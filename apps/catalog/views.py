from decimal import Decimal, InvalidOperation

from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from .models import Categoria, Producto


def _catalogo_base():
    """Productos visibles en la tienda: solo activos, con el stock total anotado, en orden estable."""
    return (
        Producto.objects.activos()
        .select_related("categoria")
        .prefetch_related("variantes")
        .con_stock_total()
        .order_by("id")
    )


@require_GET
def home(request):
    return render(request, "welcome.html", {"essentials": _catalogo_base().filter(categoria__slug="essentials")})


COLECCIONES = {"essentials": "ecommerce/essentials.html", "waves": "ecommerce/waves.html", "octane": "ecommerce/octane.html"}


@require_GET
def coleccion(request, slug):
    plantilla = COLECCIONES[slug]
    return render(request, plantilla, {"productos": _catalogo_base().filter(categoria__slug=slug)})


@require_GET
def producto_detalle(request, pk):
    producto = get_object_or_404(
        Producto.objects.activos().select_related("categoria").prefetch_related("variantes"), pk=pk
    )
    return render(request, "producto/show.html", {
        "producto": producto,
        "variantes": list(producto.variantes.all()),
        "tallas": producto.tallas,
    })


@require_GET
def catalogo(request):
    """Catálogo completo con filtros: palabra clave, categoría, precio máximo y solo disponibles."""
    q = request.GET.get("q", "").strip()
    cat = request.GET.get("cat", "").strip()
    maximo = request.GET.get("max", "").strip()
    solo_disponibles = request.GET.get("disponible") == "true"

    productos = _catalogo_base()
    if q:
        productos = productos.filter(Q(nombre__icontains=q) | Q(descripcion__icontains=q))
    if cat.isdigit():
        productos = productos.filter(categoria_id=int(cat))
    try:
        if maximo:
            productos = productos.filter(precio__lte=Decimal(maximo))
    except InvalidOperation:
        maximo = ""
    if solo_disponibles:
        productos = productos.filter(stock_total_db__gt=0)

    return render(request, "ecommerce/buscar.html", {
        "productos": productos,
        "categorias": Categoria.objects.filter(estado=True),
        "query": q,
        "cat_seleccionada": int(cat) if cat.isdigit() else None,
        "max_precio": maximo,
        "solo_disponibles": solo_disponibles,
    })
