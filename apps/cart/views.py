from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from .services import CarritoError, CarritoService


def _entero(valor, defecto=0) -> int:
    try:
        return int(valor)
    except (TypeError, ValueError):
        return defecto


@require_GET
@never_cache
def carrito_view(request):
    svc = CarritoService(request)
    lineas = svc.lineas()
    return render(request, "cart/index.html", {
        "lineas": lineas,
        "total": sum((l.subtotal for l in lineas), 0),
        "hay_problemas": any(not l.disponible for l in lineas),
    })


@require_POST
def agregar_view(request, pk):
    try:
        CarritoService(request).agregar(pk, request.POST.get("varianteId") or None, request.POST.get("talla", ""),
                                        request.POST.get("cantidad", 1))
    except CarritoError as exc:
        messages.error(request, str(exc))
        return redirect("producto", pk=pk)
    return redirect("carrito")


@require_POST
def actualizar_view(request):
    svc = CarritoService(request)
    linea_id = request.POST.get("linea", "")
    delta = request.POST.get("delta")  # botones − / +  (relativo a lo que hay guardado)
    if delta in ("1", "-1"):
        linea = next((l for l in svc.lineas() if l.id == linea_id), None)
        cantidad = (linea.cantidad if linea else 0) + int(delta)
    else:  # número escrito a mano
        cantidad = _entero(request.POST.get("cantidad"))
    try:
        aviso = svc.actualizar(linea_id, cantidad)
        if aviso:
            messages.warning(request, aviso)
    except CarritoError as exc:
        messages.error(request, str(exc))
    return redirect("carrito")


@require_POST
def eliminar_view(request):
    CarritoService(request).eliminar(request.POST.get("linea", ""))
    return redirect("carrito")
