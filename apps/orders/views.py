import json
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from apps.cart.services import CarritoService
from apps.catalog.models import Producto
from apps.core import ratelimit
from apps.core.utils import desglose_iva

from . import services
from .access import puede_ver_venta
from .emails import enviar_confirmacion_compra
from .forms import GarantiaForm
from .models import GarantiaReclamo, Venta
from .pdf import generar_factura_pdf

log = logging.getLogger(__name__)


@login_required
@never_cache
def checkout_view(request):
    lineas = CarritoService(request).lineas()
    if not lineas:
        return redirect("carrito")
    if any(not l.disponible for l in lineas):
        messages.error(request, "Revisa tu bolsa: hay productos agotados o con menos stock del que pediste.")
        return redirect("carrito")

    total = sum(l.subtotal for l in lineas)
    base, iva = desglose_iva(total)
    en_bolsa = {l.producto.pk for l in lineas}
    sugerencias = (
        Producto.objects.activos().con_stock_total().filter(stock_total_db__gt=0).exclude(pk__in=en_bolsa).order_by("id")[:3]
    )
    nombre = request.user.name.split(" ", 1)
    return render(request, "checkout/index.html", {
        "lineas": lineas, "total": total, "base": base, "iva": iva,
        "sugerencias": sugerencias,
        "departamentos": services.DEPARTAMENTOS,
        "nombre_inicial": nombre[0],
        "apellidos_inicial": nombre[1] if len(nombre) > 1 else "",
    })


@login_required
@require_POST
def procesar_view(request):
    try:
        datos = json.loads(request.body.decode("utf-8"))
        if not isinstance(datos, dict):
            raise ValueError
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "Solicitud inválida."}, status=400)

    try:
        entrega = services.validar_entrega(datos)
        venta = services.procesar_pedido(request.user, entrega)
    except services.EntregaInvalida as exc:
        return JsonResponse({"error": str(exc), "campos": exc.campos}, status=400)
    except services.SinStock as exc:
        return JsonResponse({"error": str(exc)}, status=409)
    except services.CarritoVacio as exc:
        return JsonResponse({"error": str(exc), "redirect": reverse("carrito")}, status=400)
    except Exception:  # noqa: BLE001
        log.exception("Error al procesar el pedido de %s", request.user)
        return JsonResponse({"error": "No pudimos procesar tu pedido. Inténtalo de nuevo en unos minutos."}, status=500)

    enviar_confirmacion_compra(venta)
    return JsonResponse({"redirect": reverse("confirmacion", args=[venta.pk])})


@login_required
@never_cache
def confirmacion_view(request, pk):
    venta = get_object_or_404(Venta.objects.select_related("usuario", "envio"), pk=pk)
    if not puede_ver_venta(request.user, venta):
        raise Http404  # igual que un pedido inexistente: no se revela qué números existen
    return render(request, "checkout/confirmacion.html", {"venta": venta, "envio": venta.envio})


# =========================================================================== factura
def _venta_visible(request, pk) -> Venta:
    """El pedido, solo si es del usuario (o es personal). Si no, 404: no se revela qué números existen."""
    venta = get_object_or_404(Venta.objects.select_related("usuario", "envio"), pk=pk)
    if not puede_ver_venta(request.user, venta):
        raise Http404
    return venta


@login_required
@never_cache
def factura_view(request, pk):
    venta = _venta_visible(request, pk)
    return render(request, "checkout/factura.html", {
        "venta": venta, "envio": venta.envio,
        "items": venta.items.select_related("producto", "variante").all(),
        "subtitulo": settings.FACTURA_SUBTITULO, "nit": settings.EMPRESA_NIT, "empresa": settings.EMPRESA_NOMBRE,
    })


@login_required
@never_cache
def factura_pdf_view(request, pk):
    venta = _venta_visible(request, pk)
    respuesta = HttpResponse(generar_factura_pdf(venta), content_type="application/pdf")
    respuesta["Content-Disposition"] = f'attachment; filename="factura-stateless-{venta.id}.pdf"'
    return respuesta


# =========================================================================== mis pedidos
@login_required
@never_cache
def pedidos_view(request):
    ventas = Venta.objects.filter(usuario=request.user).select_related("envio")
    return render(request, "cliente/pedidos/index.html", {"ventas": ventas})


@login_required
@never_cache
def pedidos_garantias_view(request):
    pedidos = list(Venta.objects.filter(usuario=request.user).prefetch_related("items__producto"))
    garantias = GarantiaReclamo.objects.filter(usuario=request.user).select_related("producto")
    # Solo las prendas de ese pedido (sin repetir la misma prenda en varias tallas)
    opciones, vistas = [], set()
    for v in pedidos:
        for item in v.items.all():
            if (v.id, item.producto_id) not in vistas:
                vistas.add((v.id, item.producto_id))
                opciones.append({"venta": v.id, "producto": item.producto_id,
                                 "texto": f"{item.producto.nombre} (Orden #{v.id})"})
    return render(request, "account/orders.html", {
        "pedidos": pedidos, "garantias": garantias, "opciones": opciones,
        "tipos": GarantiaReclamo.Tipo.choices,
    })


@login_required
@never_cache
def tracking_view(request, pk):
    venta = _venta_visible(request, pk)
    return render(request, "tracking.html", {"venta": venta, "envio": venta.envio})


@login_required
@require_POST
def garantia_radicar_view(request):
    destino = redirect("pedidos_garantias")
    form = GarantiaForm(request.POST)
    if not form.is_valid():
        errores_de_texto = [e for campo, lista in form.errors.items() if campo not in ("ventaId", "productoId") for e in lista]
        messages.error(request, errores_de_texto[0] if errores_de_texto else "Datos de pedido o prenda inválidos.")
        return destino

    datos = form.cleaned_data
    venta = Venta.objects.filter(pk=datos["ventaId"], usuario=request.user).first()
    item = venta and venta.items.filter(producto_id=datos["productoId"]).select_related("producto__proveedor").first()
    if venta is None or item is None:  # el pedido no es suyo, o la prenda no está en ese pedido
        messages.error(request, "Datos de pedido o prenda inválidos.")
        return destino
    if venta.cancelada:
        messages.error(request, "Ese pedido está cancelado, así que no admite reclamos.")
        return destino
    if not ratelimit.permitir(f"garantia:{request.user.pk}", 10, 60 * 60):
        messages.error(request, "Has enviado muchos reclamos seguidos. Inténtalo de nuevo más tarde.")
        return destino

    reclamo = GarantiaReclamo.objects.create(
        usuario=request.user, venta=venta, producto=item.producto, proveedor=item.producto.proveedor,
        tipo_incidencia=datos["tipoIncidencia"], descripcion_cliente=datos["descripcion"],
        estado=GarantiaReclamo.Estado.RADICADO,
    )
    messages.success(
        request,
        f"Tu solicitud de garantía #{reclamo.id} para la prenda '{item.producto.nombre}' fue radicada. "
        "Nuestro equipo de control de calidad y el proveedor textil asignado la están evaluando.",
    )
    return destino
