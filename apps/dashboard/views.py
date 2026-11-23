from datetime import timedelta
from functools import wraps
from io import BytesIO
from decimal import Decimal
import json
import logging

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.db.models.deletion import ProtectedError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from apps.accounts.models import Role
from apps.catalog.models import Categoria, Producto, Proveedor
from apps.core import ratelimit
from apps.core.ai import IAError, responder_ollama
from apps.core.utils import desglose_iva
from apps.orders import services as pedidos_services
from apps.orders.models import Envio, GarantiaReclamo, Venta, VentaItem

from .forms import (
    CategoriaForm,
    EnvioAdminForm,
    ProductoForm,
    ProductoImagenFormSet,
    ProductoVarianteFormSet,
    ProveedorForm,
    ReclamoAdminForm,
    ReporteFiltroForm,
    UsuarioForm,
    VentaEstadoForm,
)

User = get_user_model()
log = logging.getLogger(__name__)
ESTADOS_CERRADOS = (Venta.Estado.CANCELADO, Venta.Estado.PENDIENTE_PAGO)


def personal_required(view):
    @wraps(view)
    @login_required
    def wrapped(request, *args, **kwargs):
        if not request.user.es_personal:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapped


def _ventas_pagadas(queryset=None):
    queryset = queryset if queryset is not None else Venta.objects.all()
    return queryset.exclude(estado__in=ESTADOS_CERRADOS)


@personal_required
def inicio(request):
    hoy = timezone.localdate()
    inicio_grafica = hoy - timedelta(days=29)
    ventas_grafica = _ventas_pagadas().filter(created_at__date__gte=inicio_grafica, created_at__date__lte=hoy)
    por_dia = {
        fila["dia"]: fila["total"]
        for fila in ventas_grafica.annotate(dia=TruncDate("created_at")).values("dia").annotate(total=Sum("total"))
    }
    dias = [
        {"fecha": inicio_grafica + timedelta(days=i), "total": por_dia.get(inicio_grafica + timedelta(days=i), 0)}
        for i in range(30)
    ]
    max_dia = max((dia["total"] for dia in dias), default=0) or 1
    for dia in dias:
        dia["alto"] = max(3, round(float(dia["total"] / max_dia) * 100)) if dia["total"] else 0

    metodos = list(_ventas_pagadas().values("metodo_pago").annotate(total=Count("id")).order_by("metodo_pago"))
    cantidad_metodos = sum(fila["total"] for fila in metodos)
    colores = ("#111111", "#4b4b4b", "#777777", "#a9a9a9", "#d0d0d0")
    cursor, partes = 0, []
    for i, fila in enumerate(metodos):
        porcentaje = fila["total"] / cantidad_metodos * 100 if cantidad_metodos else 0
        partes.append(f"{colores[i % len(colores)]} {cursor:.2f}% {cursor + porcentaje:.2f}%")
        cursor += porcentaje

    return render(request, "dashboard/inicio.html", {
        "total_ventas": _ventas_pagadas().aggregate(total=Sum("total"))["total"] or 0,
        "total_pedidos": Venta.objects.count(),
        "total_clientes": User.objects.filter(role__name=Role.CLIENTE).count(),
        "total_productos": Producto.objects.count(),
        "dias": dias,
        "metodos": metodos,
        "gradiente_metodos": f"conic-gradient({', '.join(partes)})" if partes else "#ddd",
        "ventas_recientes": Venta.objects.select_related("usuario").order_by("-created_at")[:6],
    })


def _datos_panel_para_ia():
    """Contexto vigente, acotado y sin datos identificables para el modelo local."""
    ventas_pagadas = Venta.objects.exclude(estado__in=ESTADOS_CERRADOS)
    resumen_ventas = ventas_pagadas.aggregate(cantidad=Count("id"), total=Sum("total"))
    hoy = timezone.localdate()
    ventas_diarias = list(
        ventas_pagadas.filter(created_at__date__gte=hoy - timedelta(days=29), created_at__date__lte=hoy)
        .annotate(dia=TruncDate("created_at"))
        .values("dia")
        .annotate(cantidad=Count("id"), total=Sum("total"))
        .order_by("dia")
    )
    productos = list(
        Producto.objects.con_stock_total()
        .select_related("categoria")
        .order_by("nombre")[:200]
    )
    ventas_recientes = list(
        Venta.objects.order_by("-created_at", "-id")
        .values("id", "created_at", "estado", "total")[:30]
    )
    reclamos = list(
        GarantiaReclamo.objects.order_by("-created_at", "-id")
        .values("id", "created_at", "tipo_incidencia", "estado", "venta_id", "producto__nombre")[:30]
    )
    ventas_por_estado = list(
        Venta.objects.values("estado").annotate(cantidad=Count("id"), total=Sum("total")).order_by("estado")
    )
    reclamos_por_estado = list(
        GarantiaReclamo.objects.values("estado").annotate(cantidad=Count("id")).order_by("estado")
    )
    reclamos_por_tipo = list(
        GarantiaReclamo.objects.values("tipo_incidencia").annotate(cantidad=Count("id")).order_by("tipo_incidencia")
    )
    productos_mas_vendidos = list(
        VentaItem.objects.exclude(venta__estado__in=ESTADOS_CERRADOS)
        .values("producto__nombre")
        .annotate(unidades=Sum("cantidad"))
        .order_by("-unidades", "producto__nombre")[:10]
    )
    inventario = [
        {
            "producto": producto.nombre,
            "categoria": producto.categoria.nombre,
            "estado": producto.estado,
            "precio": str(producto.precio),
            "stock": producto.stock_total,
            "stock_minimo": producto.stock_minimo,
        }
        for producto in productos
    ]
    return {
        "actualizado_en": timezone.localtime().isoformat(timespec="seconds"),
        "clientes_registrados": User.objects.filter(role__name=Role.CLIENTE).count(),
        "resumen_inventario": {
            "productos_totales": Producto.objects.count(),
            "productos_activos": Producto.objects.activos().count(),
            "productos_con_stock_bajo": Producto.objects.stock_bajo().count(),
            "productos_sin_stock": Producto.objects.sin_stock().count(),
        },
        "resumen_ventas_pagadas": {
            "cantidad": resumen_ventas["cantidad"],
            "total_cop": str(resumen_ventas["total"] or Decimal("0")),
        },
        "ventas_ultimos_30_dias": [
            {"fecha": fila["dia"].isoformat(), "cantidad": fila["cantidad"], "total_cop": str(fila["total"] or 0)}
            for fila in ventas_diarias
        ],
        "ventas_por_estado": [
            {"estado": fila["estado"], "cantidad": fila["cantidad"], "total_cop": str(fila["total"] or 0)}
            for fila in ventas_por_estado
        ],
        "productos_mas_vendidos": productos_mas_vendidos,
        "inventario_hasta_200_productos": inventario,
        "reclamos_por_estado": reclamos_por_estado,
        "reclamos_por_tipo": reclamos_por_tipo,
        "pedidos_recientes_hasta_30": [
            {
                "id": fila["id"],
                "fecha": timezone.localtime(fila["created_at"]).isoformat(timespec="minutes"),
                "estado": fila["estado"],
                "total_cop": str(fila["total"]),
            }
            for fila in ventas_recientes
        ],
        "reclamos_recientes_hasta_30": [
            {
                "id": fila["id"],
                "fecha": timezone.localtime(fila["created_at"]).isoformat(timespec="minutes"),
                "tipo": fila["tipo_incidencia"],
                "estado": fila["estado"],
                "pedido_id": fila["venta_id"],
                "producto": fila["producto__nombre"],
            }
            for fila in reclamos
        ],
    }


@personal_required
@never_cache
@require_GET
def asistente(request):
    historial = request.session.get(f"asistente_admin_{request.user.pk}", [])
    return render(request, "dashboard/asistente.html", {
        "historial": historial,
        "modelo_ia": settings.OLLAMA_MODEL,
        "num_ctx": settings.OLLAMA_NUM_CTX,
    })


@personal_required
@never_cache
@require_POST
def asistente_preguntar(request):
    try:
        datos = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "La solicitud debe contener JSON válido."}, status=400)
    if not isinstance(datos, dict):
        return JsonResponse({"error": "La solicitud debe contener una pregunta."}, status=400)
    pregunta = datos.get("question")
    if not isinstance(pregunta, str) or not pregunta.strip() or len(pregunta) > 1000:
        return JsonResponse({"error": "Escribe una pregunta de hasta 1000 caracteres."}, status=400)
    if not ratelimit.permitir(f"asistente-admin:{request.user.pk}", 30, 60 * 60):
        return JsonResponse({"error": "Has enviado muchas preguntas. Inténtalo de nuevo más tarde."}, status=429)

    clave_historial = f"asistente_admin_{request.user.pk}"
    historial = request.session.get(clave_historial, [])[-5:]
    contexto = _datos_panel_para_ia()
    mensajes = [{
        "role": "system",
        "content": (
            "Eres el asistente interno de STATELESS. Responde en español, de forma clara y concisa, "
            "usando únicamente el contexto JSON más reciente que acompaña a cada pregunta. No inventes "
            "cifras ni afirmes haber ejecutado cambios. Si falta un dato, dilo explícitamente. Solo tienes "
            "acceso de lectura: nunca ejecutes ni propongas operaciones de escritura. El contexto no contiene "
            "nombres, correos, direcciones ni descripciones privadas de clientes. La hora del contexto indica "
            "cuándo se consultó la base de datos. Para presentar cantidades y dinero usa el formato de "
            "Colombia: punto para miles y coma para decimales (por ejemplo, 1.234 y $1.234.567,50 COP). "
            "Nunca uses coma como separador de miles."
        ),
    }]
    for turno in historial:
        mensajes.extend([
            {"role": "user", "content": turno["question"]},
            {"role": "assistant", "content": turno["answer"]},
        ])
    mensajes.append({
        "role": "user",
        "content": (
            f"Pregunta: {pregunta.strip()}\n\n"
            "Datos actuales consultados de la base de datos (JSON):\n"
            f"{json.dumps(contexto, ensure_ascii=False)}"
        ),
    })
    try:
        respuesta = responder_ollama(mensajes)
    except IAError as exc:
        return JsonResponse({"error": str(exc)}, status=503)
    historial.append({"question": pregunta.strip(), "answer": respuesta})
    request.session[clave_historial] = historial[-5:]
    return JsonResponse({"answer": respuesta, "updated_at": contexto["actualizado_en"]})


@personal_required
@never_cache
@require_GET
def reclamos(request):
    pendientes = GarantiaReclamo.objects.filter(
        estado__in=(GarantiaReclamo.Estado.RADICADO, GarantiaReclamo.Estado.EN_AUDITORIA)
    ).count()
    queryset = GarantiaReclamo.objects.select_related(
        "usuario", "venta", "producto", "proveedor"
    ).order_by("-created_at", "-id")
    return render(request, "dashboard/reclamos.html", {
        "reclamos": queryset,
        "pendientes": pendientes,
        "estados": GarantiaReclamo.Estado.choices,
    })


@personal_required
@require_POST
def reclamo_actualizar(request, pk):
    reclamo = get_object_or_404(GarantiaReclamo, pk=pk)
    form = ReclamoAdminForm(request.POST, instance=reclamo)
    if form.is_valid():
        form.save()
        messages.success(request, f"Se actualizó el reclamo #{reclamo.pk}.")
    else:
        messages.error(request, "Revisa el estado y la respuesta del reclamo.")
    return redirect("dashboard:reclamos")


@personal_required
def ventas(request):
    queryset = Venta.objects.select_related("usuario", "envio").order_by("-created_at", "-id")
    return render(request, "dashboard/ventas.html", {
        "ventas": queryset,
        "total_recaudado": _ventas_pagadas(queryset).aggregate(total=Sum("total"))["total"] or 0,
        "total_pedidos": queryset.count(),
        "tipo_principal": queryset.values("tipo_venta").annotate(total=Count("id")).order_by("-total").first(),
        "estados_venta": VentaEstadoForm().fields["estado"].choices,
    })


@personal_required
def venta_detalle(request, pk):
    venta = get_object_or_404(
        Venta.objects.select_related("usuario", "envio").prefetch_related("items__producto", "items__variante"),
        pk=pk,
    )
    return render(request, "dashboard/venta_detalle.html", {
        "venta": venta,
        "envio": getattr(venta, "envio", None),
        "items": venta.items.all(),
    })


@personal_required
@require_POST
def venta_estado(request, pk):
    venta = get_object_or_404(Venta, pk=pk)
    form = VentaEstadoForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Selecciona un estado de pedido válido.")
    else:
        try:
            resultado = pedidos_services.cambiar_estado(venta, estado_venta=form.cleaned_data["estado"])
        except pedidos_services.EstadoInvalido as exc:
            messages.error(request, str(exc))
        else:
            messages.success(
                request,
                "Estado actualizado." if resultado.estado_cambio else "El pedido ya tenía ese estado.",
            )
    return redirect("dashboard:ventas")


@personal_required
def usuarios(request):
    return render(request, "dashboard/usuarios.html", {
        "usuarios": User.objects.select_related("role").order_by("id"),
    })


@personal_required
def usuario_editar(request, pk):
    usuario = get_object_or_404(User, pk=pk)
    form = UsuarioForm(request.POST or None, instance=usuario)
    if usuario.es_protegido:
        form.fields["role"].disabled = True
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Usuario actualizado.")
        return redirect("dashboard:usuarios")
    return render(request, "dashboard/usuario_form.html", {"form": form, "usuario": usuario})


@personal_required
@require_POST
def usuario_estado(request, pk):
    usuario = get_object_or_404(User, pk=pk)
    if usuario.es_protegido:
        messages.error(request, "La cuenta de superusuario está protegida y no se puede inhabilitar.")
    else:
        usuario.is_active = not usuario.is_active
        usuario.save(update_fields=["is_active", "updated_at"])
        messages.success(request, "Usuario habilitado." if usuario.is_active else "Usuario inhabilitado.")
    return redirect("dashboard:usuarios")


@personal_required
def envios(request):
    filas = Envio.objects.select_related("venta", "venta__usuario").exclude(
        venta__estado=Venta.Estado.CANCELADO
    ).order_by("-venta__created_at")
    return render(request, "dashboard/envios.html", {
        "envios": filas,
        "estados_envio": EnvioAdminForm().fields["estado"].choices,
        "transportadoras": Envio.Transportadora.choices,
    })


@personal_required
@require_POST
def envio_actualizar(request, pk):
    envio = get_object_or_404(Envio.objects.select_related("venta"), pk=pk)
    form = EnvioAdminForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Revisa el estado, la transportadora y el número de guía.")
        return redirect("dashboard:envios")
    try:
        resultado = pedidos_services.cambiar_estado(
            envio.venta,
            estado_envio=form.cleaned_data["estado"],
            transportadora=form.cleaned_data["transportadora"],
            numero_guia=form.cleaned_data["numero_guia"],
            exigir_guia=True,
        )
    except pedidos_services.EstadoInvalido as exc:
        messages.error(request, str(exc))
    else:
        if resultado.estado_cambio or resultado.notificado:
            messages.success(request, "Información de envío actualizada.")
        else:
            messages.info(request, "El envío ya tenía esa información.")
    return redirect("dashboard:envios")


@personal_required
def productos(request):
    queryset = Producto.objects.con_stock_total().select_related("categoria", "proveedor").order_by("id")
    return render(request, "dashboard/productos.html", {
        "productos": queryset,
        "total_productos": Producto.objects.count(),
        "stock_bajo": Producto.objects.stock_bajo().count(),
        "sin_stock": Producto.objects.sin_stock().count(),
    })


def _producto_edicion(request, producto, titulo):
    form = ProductoForm(request.POST or None, request.FILES or None, instance=producto)
    variantes = ProductoVarianteFormSet(
        request.POST or None, request.FILES or None, instance=producto, prefix="variantes"
    )
    imagenes = ProductoImagenFormSet(
        request.POST or None, request.FILES or None, instance=producto, prefix="imagenes"
    )
    if request.method == "POST" and form.is_valid():
        if variantes.is_valid() and imagenes.is_valid():
            producto = form.save()
            variantes.instance = producto
            imagenes.instance = producto
            variantes.save()
            imagenes.save()
            messages.success(request, "Producto guardado correctamente.")
            return redirect("dashboard:productos")
    return render(request, "dashboard/producto_form.html", {
        "form": form,
        "variantes": variantes,
        "imagenes": imagenes,
        "producto": producto,
        "titulo": titulo,
    })


@personal_required
def producto_crear(request):
    return _producto_edicion(request, Producto(), "Registrar producto")


@personal_required
def producto_editar(request, pk):
    return _producto_edicion(request, get_object_or_404(Producto, pk=pk), "Editar producto")


@personal_required
@require_POST
def producto_eliminar(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    try:
        producto.delete()
    except ProtectedError:
        messages.error(request, "No se puede eliminar: el producto tiene ventas asociadas.")
    else:
        messages.success(request, "Producto eliminado.")
    return redirect("dashboard:productos")


@personal_required
def proveedores(request):
    return render(request, "dashboard/proveedores.html", {
        "proveedores": Proveedor.objects.order_by("id"),
    })


def _proveedor_edicion(request, proveedor, titulo):
    form = ProveedorForm(request.POST or None, instance=proveedor)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Proveedor guardado correctamente.")
        return redirect("dashboard:proveedores")
    return render(request, "dashboard/entidad_form.html", {
        "form": form, "titulo": titulo, "cancel_url": "dashboard:proveedores",
    })


@personal_required
def proveedor_crear(request):
    return _proveedor_edicion(request, Proveedor(), "Registrar proveedor")


@personal_required
def proveedor_editar(request, pk):
    return _proveedor_edicion(request, get_object_or_404(Proveedor, pk=pk), "Editar proveedor")


@personal_required
@require_POST
def proveedor_eliminar(request, pk):
    proveedor = get_object_or_404(Proveedor, pk=pk)
    try:
        proveedor.delete()
    except ProtectedError:
        messages.error(request, "No se puede eliminar: el proveedor está asociado a productos.")
    else:
        messages.success(request, "Proveedor eliminado.")
    return redirect("dashboard:proveedores")


@personal_required
def categorias(request):
    return render(request, "dashboard/categorias.html", {
        "categorias": Categoria.objects.order_by("id"),
    })


def _categoria_edicion(request, categoria, titulo):
    form = CategoriaForm(request.POST or None, instance=categoria)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Categoría guardada correctamente.")
        return redirect("dashboard:categorias")
    return render(request, "dashboard/entidad_form.html", {
        "form": form, "titulo": titulo, "cancel_url": "dashboard:categorias",
    })


@personal_required
def categoria_crear(request):
    return _categoria_edicion(request, Categoria(), "Registrar categoría")


@personal_required
def categoria_editar(request, pk):
    return _categoria_edicion(request, get_object_or_404(Categoria, pk=pk), "Editar categoría")


@personal_required
@require_POST
def categoria_eliminar(request, pk):
    categoria = get_object_or_404(Categoria, pk=pk)
    if categoria.es_base:
        messages.error(request, "Las colecciones principales no se pueden eliminar.")
    else:
        try:
            categoria.delete()
        except ProtectedError:
            messages.error(request, "No se puede eliminar: la categoría tiene productos asociados.")
        else:
            messages.success(request, "Categoría eliminada.")
    return redirect("dashboard:categorias")


def _reporte_ventas(form):
    queryset = _ventas_pagadas().select_related("usuario").order_by("-created_at", "-id")
    if form.is_valid():
        desde, hasta = form.cleaned_data["desde"], form.cleaned_data["hasta"]
        if desde:
            queryset = queryset.filter(created_at__date__gte=desde)
        if hasta:
            queryset = queryset.filter(created_at__date__lte=hasta)
    elif form.is_bound:
        queryset = queryset.none()
    return queryset


@personal_required
def reportes(request):
    form = ReporteFiltroForm(request.GET or None)
    ventas_filtradas = list(_reporte_ventas(form))
    total = sum((venta.total for venta in ventas_filtradas), Decimal("0"))
    base = sum((venta.base_neta for venta in ventas_filtradas), Decimal("0"))
    iva = sum((venta.iva for venta in ventas_filtradas), Decimal("0"))
    cantidad = len(ventas_filtradas)
    return render(request, "dashboard/reportes.html", {
        "ventas": ventas_filtradas,
        "form": form,
        "total": total,
        "base": base,
        "iva": iva,
        "cantidad": cantidad,
        "ticket_promedio": total / cantidad if cantidad else 0,
    })


@personal_required
def reporte_exportar(request):
    form = ReporteFiltroForm(request.GET or None)
    ventas_filtradas = _reporte_ventas(form)
    if form.is_bound and not form.is_valid():
        messages.error(request, "Corrige las fechas antes de exportar el informe.")
        return redirect("dashboard:reportes")

    libro = Workbook()
    hoja = libro.active
    hoja.title = "Ventas"
    hoja.append(["Pedido", "Fecha", "Cliente", "Correo", "Método de pago", "Base neta", "IVA (19%)", "Total", "Estado"])
    for cell in hoja[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="111111")

    for venta in ventas_filtradas:
        base, iva = desglose_iva(venta.total)
        hoja.append([
            venta.numero_factura,
            timezone.localtime(venta.created_at).replace(tzinfo=None),
            _texto_excel(venta.usuario.name),
            _texto_excel(venta.usuario.email),
            _texto_excel(venta.get_metodo_pago_display()),
            float(base),
            float(iva),
            float(venta.total),
            _texto_excel(venta.get_estado_display()),
        ])
    for columna in hoja.columns:
        ancho = max(len(str(celda.value or "")) for celda in columna)
        hoja.column_dimensions[columna[0].column_letter].width = min(ancho + 2, 40)
    hoja.freeze_panes = "A2"

    salida = BytesIO()
    libro.save(salida)
    respuesta = HttpResponse(
        salida.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    respuesta["Content-Disposition"] = 'attachment; filename="reporte-financiero-stateless.xlsx"'
    return respuesta


def _texto_excel(valor):
    texto = str(valor or "")
    return f"'{texto}" if texto.lstrip().startswith(("=", "+", "-", "@")) else texto
