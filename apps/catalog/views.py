import json
from decimal import Decimal, InvalidOperation

from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.core import ratelimit
from apps.core.ai import IAError
from .models import Categoria, Producto
from .ai import recomendar_prendas


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


@require_POST
def recomendar_view(request, pk):
    producto = get_object_or_404(
        Producto.objects.activos().select_related("categoria").prefetch_related("variantes"), pk=pk
    )
    try:
        datos = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "La solicitud debe contener JSON válido."}, status=400)
    if not isinstance(datos, dict):
        return JsonResponse({"error": "La solicitud de recomendaciones no es válida."}, status=400)
    solicitud = datos.get("request", "")
    if not isinstance(solicitud, str) or len(solicitud) > 500:
        return JsonResponse({"error": "La petición debe tener máximo 500 caracteres."}, status=400)
    ip = ratelimit.ip_del_cliente(request)
    if not ratelimit.permitir(f"recomendaciones-ia:{ip}", 20, 60 * 60):
        return JsonResponse({"error": "Has solicitado muchas recomendaciones. Inténtalo más tarde."}, status=429)
    try:
        recomendaciones = recomendar_prendas(producto, solicitud.strip())
    except IAError as exc:
        return JsonResponse({"error": str(exc)}, status=503)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=502)
    return JsonResponse({
        "recommendations": [
            {
                "id": item["producto"].pk,
                "name": item["producto"].nombre,
                "price": str(item["producto"].precio),
                "url": reverse("producto", args=[item["producto"].pk]),
                "reason": item["razon"],
            }
            for item in recomendaciones
        ]
    })


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
