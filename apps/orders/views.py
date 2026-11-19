import logging
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from apps.catalog.models import Producto, ProductoVariante
from apps.cart.models import Carrito
from apps.payments import services as payment_services

from .forms import CheckoutForm
from .models import Envio, Venta, VentaItem

logger = logging.getLogger(__name__)


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def checkout(request):
    form = CheckoutForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        sale = None
        issue = ""
        with transaction.atomic():
            cart = Carrito.objects.select_for_update().filter(user=request.user).first()
            items = list(
                cart.items.select_for_update().select_related("producto", "variante").all()
            ) if cart else []
            if not items:
                issue = "Tu carrito está vacío."
            else:
                product_ids = sorted({item.producto_id for item in items})
                products = {
                    product.pk: product
                    for product in Producto.objects.select_for_update()
                    .select_related("categoria")
                    .filter(pk__in=product_ids)
                    .order_by("pk")
                }
                variant_ids = sorted({item.variante_id for item in items if item.variante_id})
                variants = {
                    variant.pk: variant
                    for variant in ProductoVariante.objects.select_for_update()
                    .filter(pk__in=variant_ids)
                    .order_by("pk")
                }
                for item in items:
                    product = products.get(item.producto_id)
                    variant = variants.get(item.variante_id)
                    if product is None or product.estado != Producto.Estado.ACTIVO:
                        issue = f"El producto {item.producto.nombre} ya no está disponible."
                        break
                    if item.variante_id and (
                        variant is None or variant.producto_id != product.pk
                    ):
                        issue = f"La variante de {product.nombre} ya no está disponible."
                        break
                    available = variant.stock_actual if variant else product.stock_actual
                    if item.cantidad > available:
                        issue = (
                            f"Solo quedan {available} unidad(es) de {product.nombre} "
                            "para la opción seleccionada."
                        )
                        break
                    if product.requiere_talla and item.talla not in product.tallas:
                        issue = f"La talla de {product.nombre} ya no está disponible."
                        break
                if not issue:
                    total = sum(
                        (item.precio_unitario * item.cantidad for item in items),
                        Decimal("0"),
                    )
                    sale = Venta.objects.create(
                        usuario=request.user,
                        metodo_pago=Venta.Metodo.MERCADO_PAGO,
                        total=total,
                    )
                    VentaItem.objects.bulk_create(
                        [
                            VentaItem(
                                venta=sale,
                                producto=item.producto,
                                variante=item.variante,
                                talla=item.talla,
                                cantidad=item.cantidad,
                                precio_unitario=item.precio_unitario,
                            )
                            for item in items
                        ]
                    )
                    Envio.objects.create(
                        venta=sale,
                        **form.cleaned_data,
                    )
                    cart.items.all().delete()

        if issue:
            form.add_error(None, issue)
        else:
            messages.success(request, "Creamos tu pedido. Ahora puedes continuar al pago.")
            return redirect("pedido_detalle", order_id=sale.pk)

    items = list(request.user.carrito.items.select_related("producto", "variante")) \
        if hasattr(request.user, "carrito") else []
    if not items:
        messages.info(request, "Agrega productos antes de finalizar la compra.")
        return redirect("carrito")
    total = sum((item.subtotal for item in items), Decimal("0"))
    return render(
        request,
        "orders/checkout.html",
        {"form": form, "items": items, "total": total},
    )


@login_required
@never_cache
def pedidos(request):
    orders = (
        Venta.objects.filter(usuario=request.user)
        .select_related("envio")
        .prefetch_related("items__producto")
    )
    return render(request, "orders/list.html", {"orders": orders})


@login_required
@never_cache
def pedido_detalle(request, order_id):
    order = get_object_or_404(
        Venta.objects.select_related("envio").prefetch_related("items__producto", "items__variante"),
        pk=order_id,
        usuario=request.user,
    )
    payment = order.pagos.first()
    shipment = Envio.objects.filter(venta=order).first()
    return render(
        request,
        "orders/detail.html",
        {
            "order": order,
            "payment": payment,
            "shipment": shipment,
            "payment_result": request.GET.get("pago", ""),
        },
    )


@login_required
@require_POST
def pagar_pedido(request, order_id):
    order = get_object_or_404(
        Venta,
        pk=order_id,
        usuario=request.user,
        estado=Venta.Estado.PENDIENTE_PAGO,
    )
    try:
        payment, _ = payment_services.create_payment_preference(order)
    except payment_services.MercadoPagoError as error:
        logger.warning("No se pudo iniciar pago del pedido %s: %s", order.pk, error)
        messages.error(request, str(error))
        return redirect("pedido_detalle", order_id=order.pk)

    destination = (
        payment.sandbox_init_point
        if settings.DEBUG and payment.sandbox_init_point
        else payment.init_point
    )
    if not destination:
        messages.error(request, "Mercado Pago no devolvió el enlace para pagar. Inténtalo más tarde.")
        return redirect("pedido_detalle", order_id=order.pk)
    return redirect(destination)


@login_required
@user_passes_test(lambda user: user.es_personal)
@never_cache
def dashboard(request):
    orders = Venta.objects.select_related("usuario").order_by("-created_at")
    totals = {
        "orders": orders.count(),
        "pending": orders.filter(estado=Venta.Estado.PENDIENTE_PAGO).count(),
        "confirmed": orders.filter(estado=Venta.Estado.PAGO_CONFIRMADO).count(),
        "revenue": sum(
            orders.filter(estado__in=[
                Venta.Estado.PAGO_CONFIRMADO,
                Venta.Estado.EN_PREPARACION,
                Venta.Estado.ENVIADO,
                Venta.Estado.ENTREGADO,
            ]).values_list("total", flat=True),
            Decimal("0"),
        ),
    }
    return render(
        request,
        "orders/dashboard.html",
        {"orders": orders[:10], "totals": totals},
    )
