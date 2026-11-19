from decimal import Decimal

from django.contrib import messages
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from apps.catalog.models import Producto

from .services import (
    CartValidationError,
    add_item,
    get_cart_lines,
    remove_item,
    update_item,
)


@never_cache
def carrito_view(request):
    if request.method == "POST":
        action = request.POST.get("action")
        key = request.POST.get("key", "")
        try:
            if action == "update":
                quantity = int(request.POST.get("cantidad", ""))
                update_item(request, key, quantity)
                messages.success(request, "Actualizamos tu carrito.")
            elif action == "remove":
                remove_item(request, key)
                messages.success(request, "Quitamos el producto de tu carrito.")
            else:
                messages.error(request, "La acción solicitada no es válida.")
        except CartValidationError as error:
            messages.error(request, str(error))
        except ValueError:
            messages.error(request, "Ingresa una cantidad válida.")
        return redirect("carrito")
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET", "POST"])

    items = get_cart_lines(request)
    return render(
        request,
        "cart/cart.html",
        {
            "items": items,
            "total": sum((item.subtotal for item in items), Decimal("0")),
            "cart_count": sum(item.cantidad for item in items),
        },
    )


@require_POST
def agregar_carrito(request, product_id):
    producto = get_object_or_404(Producto.objects.activos(), pk=product_id)
    try:
        quantity = int(request.POST.get("cantidad", "1"))
        raw_variant_id = request.POST.get("variante_id", "")
        variant_id = int(raw_variant_id) if raw_variant_id else None
        if variant_id == 0:
            variant_id = None
    except ValueError:
        messages.error(request, "La cantidad o el color seleccionado no son válidos.")
        return redirect("producto", product_id=producto.pk)

    try:
        add_item(
            request,
            producto.pk,
            variant_id,
            request.POST.get("talla", "").strip(),
            quantity,
        )
    except CartValidationError as error:
        messages.error(request, str(error))
        return redirect("producto", product_id=producto.pk)

    messages.success(request, "Agregamos el producto a tu carrito.")
    return redirect("carrito")
