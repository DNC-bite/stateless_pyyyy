import re
import uuid
from collections import defaultdict

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.cart.services import AlmacenBD
from apps.catalog.models import Producto, ProductoVariante

from .models import Envio, Venta, VentaItem

DEPARTAMENTOS = [
    "Amazonas", "Antioquia", "Arauca", "Atlántico", "Bogotá D.C.", "Bolívar", "Boyacá", "Caldas", "Caquetá",
    "Casanare", "Cauca", "Cesar", "Chocó", "Córdoba", "Cundinamarca", "Guainía", "Guaviare", "Huila",
    "La Guajira", "Magdalena", "Meta", "Nariño", "Norte de Santander", "Putumayo", "Quindío", "Risaralda",
    "San Andrés y Providencia", "Santander", "Sucre", "Tolima", "Valle del Cauca", "Vaupés", "Vichada",
]

# Los que ofrece la pantalla de pago hoy; Efecty, Nequi y PSE siguen aceptándose en el servidor.
METODOS_VALIDOS = {m for m in Venta.Metodo.values if m != Venta.Metodo.TARJETA}


class PedidoError(Exception):
    """Error que se le muestra al cliente tal cual."""


class EntregaInvalida(PedidoError):
    def __init__(self, campos: dict):
        super().__init__("Revisa los datos de entrega: " + "; ".join(campos.values()))
        self.campos = campos


class CarritoVacio(PedidoError):
    pass


class SinStock(PedidoError):
    pass


def validar_entrega(datos: dict) -> dict:
    """Limpia y valida lo que llega del formulario de pago. Nada de esto se confía al navegador."""
    limpio, errores = {}, {}

    def texto(clave, etiqueta, maximo, obligatorio=True):
        valor = " ".join(str(datos.get(clave) or "").split())
        if obligatorio and not valor:
            errores[clave] = f"{etiqueta} es obligatorio."
        elif len(valor) > maximo:
            errores[clave] = f"{etiqueta} es demasiado largo."
        limpio[clave] = valor

    texto("nombre", "El nombre", 80)
    texto("apellidos", "Los apellidos", 80)
    texto("direccion", "La dirección", 255)
    texto("apartamento", "El complemento de dirección", 120, obligatorio=False)
    texto("ciudad", "La ciudad", 100)
    texto("departamento", "El departamento", 60)
    texto("codigo_postal", "El código postal", 12)
    texto("telefono", "El teléfono", 20)

    if limpio["departamento"] and limpio["departamento"] not in DEPARTAMENTOS:
        errores["departamento"] = "Elige un departamento de la lista."
    if limpio["telefono"] and not re.fullmatch(r"[0-9+()\s-]{7,20}", limpio["telefono"]):
        errores["telefono"] = "El teléfono no es válido."
    if limpio["codigo_postal"] and not re.fullmatch(r"[0-9A-Za-z -]{3,12}", limpio["codigo_postal"]):
        errores["codigo_postal"] = "El código postal no es válido."

    metodo = str(datos.get("metodo_pago") or "")
    if metodo not in METODOS_VALIDOS:
        errores["metodo_pago"] = "Elige un método de pago válido."
    limpio["metodo_pago"] = metodo

    if errores:
        raise EntregaInvalida(errores)
    limpio["destinatario"] = f"{limpio['nombre']} {limpio['apellidos']}"
    return limpio


@transaction.atomic
def procesar_pedido(user, entrega: dict) -> Venta:
    """
    Convierte el carrito en una venta. Todo o nada: si algo falla (por ejemplo no hay stock), no se
    descuenta nada y no se crea nada. El pago es una simulación hasta que se conecte una pasarela real.
    """
    lineas = AlmacenBD(user).lineas()
    if not lineas:
        raise CarritoVacio("Tu bolsa está vacía.")

    # 1) Total de unidades que se piden de cada existencia (el color Original o cada variante).
    demanda = defaultdict(lambda: [0, ""])
    for l in lineas:
        if not l.producto.activo:
            raise SinStock(f"{l.producto.nombre} ya no está disponible. Quítalo de tu bolsa para continuar.")
        clave = ("v", l.variante.pk) if l.variante else ("p", l.producto.pk)
        demanda[clave][0] += l.cantidad
        demanda[clave][1] = l.producto.nombre + (f" ({l.variante.color})" if l.variante else "")

    # 2) Descuento atómico: solo se descuenta si todavía alcanza (protege contra compras simultáneas).
    for (tipo, pk), (cantidad, etiqueta) in sorted(demanda.items()):
        modelo = ProductoVariante if tipo == "v" else Producto
        filas = modelo.objects.filter(pk=pk, stock_actual__gte=cantidad).update(stock_actual=F("stock_actual") - cantidad)
        if filas != 1:
            disponible = modelo.objects.filter(pk=pk).values_list("stock_actual", flat=True).first() or 0
            raise SinStock(f"No hay stock suficiente de {etiqueta}. Disponible: {disponible}.")

    # 3) Venta, ítems y envío.
    metodo = entrega["metodo_pago"]
    efecty = metodo == Venta.Metodo.EFECTY
    total = sum(l.subtotal for l in lineas)
    venta = Venta.objects.create(
        usuario=user,
        metodo_pago=metodo,
        total=total,
        estado=Venta.Estado.PENDIENTE_PAGO if efecty else Venta.Estado.PAGO_CONFIRMADO,
        codigo_pago=f"EFY-{uuid.uuid4().hex[:8].upper()}" if efecty else "",
    )
    VentaItem.objects.bulk_create([
        VentaItem(venta=venta, producto=l.producto, variante=l.variante, talla=l.talla, cantidad=l.cantidad,
                  precio_unitario=l.precio_unitario)
        for l in lineas
    ])
    Envio.objects.create(
        venta=venta,
        destinatario=entrega["destinatario"], telefono=entrega["telefono"], direccion=entrega["direccion"],
        apartamento=entrega["apartamento"], ciudad=entrega["ciudad"], departamento=entrega["departamento"],
        codigo_postal=entrega["codigo_postal"], estado=Envio.Estado.PENDIENTE,
        fecha_confirmado=None if efecty else timezone.now(),
    )
    AlmacenBD(user).vaciar()
    return venta


# =========================================================================== cambios de estado
class EstadoInvalido(PedidoError):
    pass


class ResultadoCambio:
    def __init__(self, estado_cambio: bool, notificado: bool):
        self.estado_cambio = estado_cambio
        self.notificado = notificado  # se envió el correo de logística


# Estado del pedido (venta) que corresponde a cada estado del envío, y viceversa.
VENTA_SEGUN_ENVIO = {
    Envio.Estado.PREPARANDO: Venta.Estado.EN_PREPARACION,
    Envio.Estado.EN_CURSO: Venta.Estado.ENVIADO,
    Envio.Estado.ENTREGADO: Venta.Estado.ENTREGADO,
}
ENVIO_SEGUN_VENTA = {
    Venta.Estado.PAGO_CONFIRMADO: Envio.Estado.PENDIENTE,
    Venta.Estado.EN_PREPARACION: Envio.Estado.PREPARANDO,
    Venta.Estado.ENVIADO: Envio.Estado.EN_CURSO,
    Venta.Estado.ENTREGADO: Envio.Estado.ENTREGADO,
}
CAMPO_FECHA = {
    Envio.Estado.PREPARANDO: "fecha_preparando",
    Envio.Estado.EN_CURSO: "fecha_en_curso",
    Envio.Estado.ENTREGADO: "fecha_entregado",
}


def cambiar_estado(venta, *, estado_venta=None, estado_envio=None, transportadora=None, numero_guia=None,
                   exigir_guia=False, notificar=True) -> ResultadoCambio:
    """
    ÚNICA puerta para mover un pedido por su ciclo de vida. Mantiene sincronizados el estado de la venta y el
    del envío (antes vivían separados y se contradecían), llena las fechas del envío y avisa al cliente por
    correo solo cuando algo cambió de verdad. Los pedidos cancelados quedan cerrados.
    Pasa `estado_venta` (desde la lista de ventas) o `estado_envio` (desde la pantalla de envíos).
    """
    with transaction.atomic():
        venta = Venta.objects.select_for_update().select_related("usuario").get(pk=venta.pk)
        envio = Envio.objects.select_for_update().get(venta=venta)

        if venta.cancelada:
            raise EstadoInvalido("Este pedido está cancelado y ya no se puede modificar.")

        if estado_envio is not None:
            if estado_envio not in (Envio.Estado.PENDIENTE, Envio.Estado.PREPARANDO, Envio.Estado.EN_CURSO,
                                    Envio.Estado.ENTREGADO):
                raise EstadoInvalido("Estado de envío no válido.")
            nuevo_envio = estado_envio
            nuevo_venta = VENTA_SEGUN_ENVIO.get(estado_envio)
            if nuevo_venta is None:  # volver a "pendiente": la venta solo retrocede si ya estaba avanzada
                nuevo_venta = (Venta.Estado.PAGO_CONFIRMADO if venta.estado in (
                    Venta.Estado.EN_PREPARACION, Venta.Estado.ENVIADO, Venta.Estado.ENTREGADO) else venta.estado)
        elif estado_venta is not None:
            if estado_venta == Venta.Estado.CANCELADO:
                raise EstadoInvalido("Un pedido solo se cancela con el procedimiento de cancelación excepcional.")
            if estado_venta not in Venta.Estado.values:
                raise EstadoInvalido("Estado de pedido no válido.")
            nuevo_venta = estado_venta
            nuevo_envio = ENVIO_SEGUN_VENTA.get(estado_venta, envio.estado)
        else:
            raise EstadoInvalido("No se indicó ningún estado.")

        transportadora = envio.transportadora if transportadora is None else transportadora
        numero_guia = envio.numero_guia if numero_guia is None else numero_guia.strip()
        if transportadora and transportadora not in Envio.Transportadora.values:
            raise EstadoInvalido("Transportadora no válida.")
        if exigir_guia and nuevo_envio in (Envio.Estado.EN_CURSO, Envio.Estado.ENTREGADO) \
                and not (transportadora and numero_guia):
            raise EstadoInvalido("Para marcar el envío en camino o entregado indica la transportadora y el número de guía.")

        estado_cambio = (venta.estado, envio.estado) != (nuevo_venta, nuevo_envio)
        guia_cambio = (envio.transportadora, envio.numero_guia) != (transportadora, numero_guia)

        if venta.estado != nuevo_venta:
            venta.estado = nuevo_venta
            venta.save(update_fields=["estado", "updated_at"])
        if envio.estado != nuevo_envio and nuevo_envio in CAMPO_FECHA:
            setattr(envio, CAMPO_FECHA[nuevo_envio], timezone.now())
        if nuevo_venta == Venta.Estado.PAGO_CONFIRMADO and not envio.fecha_confirmado:
            envio.fecha_confirmado = timezone.now()
        envio.estado, envio.transportadora, envio.numero_guia = nuevo_envio, transportadora, numero_guia
        envio.save()

    avisar = notificar and (estado_cambio or guia_cambio) and nuevo_envio != Envio.Estado.PENDIENTE
    notificado = False
    if avisar:
        from .emails import enviar_actualizacion_logistica

        notificado = enviar_actualizacion_logistica(venta)
    return ResultadoCambio(estado_cambio, notificado)
