"""
Carrito de compras.

- Usuario con sesión iniciada: se guarda en la base de datos (modelos Carrito / CarritoItem).
- Invitado: se guarda en la sesión del navegador. Al iniciar sesión se une al carrito del usuario.

Reglas (corrigen al sistema anterior): cada línea se identifica por producto + color + talla (la misma
camisa en M y en L son líneas distintas), agregar un producto repetido suma la cantidad pedida, y nunca se
puede pedir más de lo que hay en stock.
"""
import logging
import uuid
from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Sum

from apps.catalog.models import Producto, ProductoVariante

from .models import Carrito, CarritoItem

log = logging.getLogger(__name__)

SESSION_KEY = "guest_cart"
MAX_POR_LINEA = 99


class CarritoError(Exception):
    """Un problema que el cliente puede entender y corregir (se muestra tal cual)."""


@dataclass
class Linea:
    id: str
    producto: Producto
    variante: ProductoVariante | None
    talla: str
    cantidad: int
    precio_unitario: Decimal

    @property
    def subtotal(self) -> Decimal:
        return self.precio_unitario * self.cantidad

    @property
    def stock_disponible(self) -> int:
        return self.variante.stock_actual if self.variante else self.producto.stock_actual

    @property
    def problema(self) -> str:
        if not self.producto.activo:
            return "Este producto ya no está disponible."
        if self.stock_disponible <= 0:
            return "Agotado."
        if self.cantidad > self.stock_disponible:
            return f"Solo quedan {self.stock_disponible} unidades."
        return ""

    @property
    def disponible(self) -> bool:
        return not self.problema


# --------------------------------------------------------------------------- almacenes
class AlmacenBD:
    def __init__(self, user):
        self.user = user

    def _carrito(self, crear=False):
        if crear:
            return Carrito.objects.get_or_create(user=self.user)[0]
        return Carrito.objects.filter(user=self.user).first()

    def lineas(self):
        carrito = self._carrito()
        if not carrito:
            return []
        items = carrito.items.select_related("producto__categoria", "variante").all()
        return [Linea(str(i.id), i.producto, i.variante, i.talla, i.cantidad, i.precio_unitario) for i in items]

    def buscar(self, producto, variante, talla):
        carrito = self._carrito()
        item = carrito and carrito.items.filter(producto=producto, variante=variante, talla=talla).first()
        return Linea(str(item.id), producto, variante, talla, item.cantidad, item.precio_unitario) if item else None

    def crear(self, producto, variante, talla, cantidad, precio):
        CarritoItem.objects.create(carrito=self._carrito(crear=True), producto=producto, variante=variante,
                                   talla=talla, cantidad=cantidad, precio_unitario=precio)

    def fijar_cantidad(self, linea_id, cantidad):
        CarritoItem.objects.filter(pk=linea_id, carrito__user=self.user).update(cantidad=cantidad)

    def eliminar(self, linea_id):
        CarritoItem.objects.filter(pk=linea_id, carrito__user=self.user).delete()

    def vaciar(self):
        CarritoItem.objects.filter(carrito__user=self.user).delete()


class AlmacenSesion:
    def __init__(self, session):
        self.session = session

    def _datos(self):
        return list(self.session.get(SESSION_KEY, []))

    def _guardar(self, datos):
        self.session[SESSION_KEY] = datos
        self.session.modified = True

    def lineas(self):
        datos = self._datos()
        if not datos:
            return []
        productos = Producto.objects.select_related("categoria").in_bulk({d["p"] for d in datos})
        variantes = ProductoVariante.objects.in_bulk({d["v"] for d in datos if d["v"]})
        lineas = []
        for d in datos:
            producto = productos.get(d["p"])
            if producto is None:  # el producto ya no existe: se descarta la línea
                continue
            lineas.append(Linea(d["k"], producto, variantes.get(d["v"]) if d["v"] else None, d["t"], d["c"],
                                Decimal(d["pr"])))
        return lineas

    def buscar(self, producto, variante, talla):
        for d in self._datos():
            if d["p"] == producto.pk and d["v"] == (variante.pk if variante else None) and d["t"] == talla:
                return Linea(d["k"], producto, variante, talla, d["c"], Decimal(d["pr"]))
        return None

    def crear(self, producto, variante, talla, cantidad, precio):
        datos = self._datos()
        datos.append({"k": uuid.uuid4().hex[:10], "p": producto.pk, "v": variante.pk if variante else None,
                      "t": talla, "c": cantidad, "pr": str(precio)})
        self._guardar(datos)

    def fijar_cantidad(self, linea_id, cantidad):
        datos = self._datos()
        for d in datos:
            if d["k"] == linea_id:
                d["c"] = cantidad
        self._guardar(datos)

    def eliminar(self, linea_id):
        self._guardar([d for d in self._datos() if d["k"] != linea_id])

    def vaciar(self):
        self.session.pop(SESSION_KEY, None)
        self.session.modified = True


# --------------------------------------------------------------------------- servicio
class CarritoService:
    def __init__(self, request):
        self.almacen = AlmacenBD(request.user) if request.user.is_authenticated else AlmacenSesion(request.session)

    def lineas(self):
        return self.almacen.lineas()

    def total(self) -> Decimal:
        return sum((l.subtotal for l in self.lineas()), Decimal("0"))

    def cantidad_total(self) -> int:
        return sum(l.cantidad for l in self.lineas())

    def hay_problemas(self) -> bool:
        return any(not l.disponible for l in self.lineas())

    def agregar(self, producto_id, variante_id=None, talla="", cantidad=1):
        agregar_a_almacen(self.almacen, producto_id, variante_id, talla, cantidad)

    def actualizar(self, linea_id, cantidad) -> str:
        """Devuelve un aviso (o "") cuando la cantidad pedida se ajustó al stock."""
        linea = next((l for l in self.lineas() if l.id == str(linea_id)), None)
        if linea is None:
            raise CarritoError("Ese producto ya no está en tu bolsa.")
        if cantidad <= 0:
            self.almacen.eliminar(linea.id)
            return ""
        cantidad = min(cantidad, MAX_POR_LINEA)
        if linea.stock_disponible <= 0:
            raise CarritoError(f"{linea.producto.nombre} está agotado.")
        aviso = ""
        if cantidad > linea.stock_disponible:
            cantidad = linea.stock_disponible
            aviso = f"Solo quedan {cantidad} unidades de {linea.producto.nombre}; ajustamos tu cantidad."
        self.almacen.fijar_cantidad(linea.id, cantidad)
        return aviso

    def eliminar(self, linea_id):
        self.almacen.eliminar(str(linea_id))

    def vaciar(self):
        self.almacen.vaciar()


def agregar_a_almacen(almacen, producto_id, variante_id, talla, cantidad):
    """Valida y agrega. Usado por el carrito normal y al unir el carrito de invitado."""
    producto = Producto.objects.select_related("categoria").filter(pk=producto_id, estado=Producto.Estado.ACTIVO).first()
    if producto is None:
        raise CarritoError("Ese producto ya no está disponible.")

    variante = None
    if variante_id:
        variante = ProductoVariante.objects.filter(pk=variante_id, producto=producto).first()
        if variante is None:
            raise CarritoError("El color elegido no existe para este producto.")

    talla = (talla or "").strip().upper()
    if producto.requiere_talla:
        if not talla:
            raise CarritoError("Selecciona una talla antes de añadir al carrito.")
        if talla not in producto.tallas:
            raise CarritoError("La talla elegida no es válida para este producto.")
    else:
        talla = ""

    try:
        cantidad = max(1, int(cantidad or 1))
    except (TypeError, ValueError):
        cantidad = 1

    stock = variante.stock_actual if variante else producto.stock_actual
    if stock <= 0:
        raise CarritoError(f"{producto.nombre} está agotado.")

    existente = almacen.buscar(producto, variante, talla)
    nueva = (existente.cantidad if existente else 0) + cantidad
    if nueva > min(stock, MAX_POR_LINEA):
        ya = f" (ya tienes {existente.cantidad} en tu bolsa)" if existente else ""
        raise CarritoError(f"Solo quedan {stock} unidades de {producto.nombre}{ya}.")

    if existente:
        almacen.fijar_cantidad(existente.id, nueva)
    else:
        almacen.crear(producto, variante, talla, cantidad, producto.precio)  # el precio se congela aquí


def cantidad_en_bolsa(request) -> int:
    """Número que muestra el menú. Se calcula en cada página, así nunca queda desactualizado."""
    if request.user.is_authenticated:
        return CarritoItem.objects.filter(carrito__user=request.user).aggregate(n=Sum("cantidad"))["n"] or 0
    return sum(d.get("c", 0) for d in request.session.get(SESSION_KEY, []))


def migrar_carrito_de_sesion(request, user) -> None:
    """Al iniciar sesión: pasa lo que el invitado puso en su bolsa al carrito de su cuenta."""
    datos = request.session.pop(SESSION_KEY, None)
    if not datos:
        return
    destino = AlmacenBD(user)
    for d in datos:
        try:
            agregar_a_almacen(destino, d["p"], d["v"], d["t"], d["c"])
        except CarritoError as exc:  # p. ej. se agotó mientras tanto: se omite esa línea
            log.info("Línea del carrito de invitado omitida al iniciar sesión: %s", exc)
