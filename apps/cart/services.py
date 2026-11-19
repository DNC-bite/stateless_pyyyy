from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db import transaction

from apps.catalog.models import Producto, ProductoVariante

from .models import Carrito, CarritoItem

SESSION_CART_KEY = "cart_items"


class CartValidationError(Exception):
    pass


@dataclass
class CartLine:
    key: str
    producto: Producto
    variante: ProductoVariante | None
    talla: str
    cantidad: int
    precio_unitario: Decimal

    @property
    def subtotal(self):
        return self.precio_unitario * self.cantidad


def _session_cart(request):
    stored = request.session.get(SESSION_CART_KEY, {})
    if not isinstance(stored, dict):
        return {}
    cart = {}
    for key, item in stored.items():
        if not isinstance(item, dict):
            continue
        try:
            product_id = int(item["producto_id"])
            quantity = int(item["cantidad"])
            variant_id = int(item["variante_id"]) if item.get("variante_id") else None
            price = Decimal(str(item["precio_unitario"]))
        except (InvalidOperation, KeyError, TypeError, ValueError):
            continue
        if (
            product_id > 0
            and quantity > 0
            and (variant_id is None or variant_id > 0)
            and price.is_finite()
            and price > 0
        ):
            cart[str(key)] = {
                "producto_id": product_id,
                "variante_id": variant_id,
                "talla": str(item.get("talla", "")),
                "cantidad": quantity,
                "precio_unitario": str(price),
            }
    return cart


def _line_key(product_id, variant_id, size):
    return f"{product_id}:{variant_id or 0}:{size}"


def _validate(product, variant, size, quantity, already_in_cart=0):
    if product.estado != Producto.Estado.ACTIVO:
        raise CartValidationError("Este producto ya no está disponible.")
    if variant and variant.producto_id != product.pk:
        raise CartValidationError("La variante seleccionada no corresponde al producto.")
    if product.variantes.exists() and not variant and product.stock_actual <= 0:
        raise CartValidationError("Selecciona un color.")
    if product.requiere_talla and size not in product.tallas:
        raise CartValidationError("Selecciona una talla válida.")
    if not product.requiere_talla and size:
        raise CartValidationError("Este producto no tiene tallas.")
    if quantity < 1:
        raise CartValidationError("La cantidad debe ser al menos 1.")

    available = variant.stock_actual if variant else product.stock_actual
    if quantity + already_in_cart > available:
        raise CartValidationError(f"Solo hay {available} unidad(es) disponibles para esta opción.")


def add_item(request, product_id, variant_id, size, quantity):
    product = Producto.objects.select_related("categoria").get(pk=product_id)
    variant = None
    if variant_id:
        variant = ProductoVariante.objects.filter(producto=product, pk=variant_id).first()
        if variant is None:
            raise CartValidationError("La variante seleccionada no existe.")

    key = _line_key(product.pk, variant.pk if variant else None, size)
    if request.user.is_authenticated:
        with transaction.atomic():
            product = Producto.objects.select_for_update().select_related("categoria").get(pk=product_id)
            if variant_id:
                variant = ProductoVariante.objects.select_for_update().filter(
                    producto=product, pk=variant_id
                ).first()
                if variant is None:
                    raise CartValidationError("La variante seleccionada no existe.")
            cart, _ = Carrito.objects.get_or_create(user=request.user)
            item = CarritoItem.objects.select_for_update().filter(
                carrito=cart, producto=product, variante=variant, talla=size
            ).first()
            already = item.cantidad if item else 0
            _validate(product, variant, size, quantity, already)
            if item:
                item.cantidad += quantity
                item.save(update_fields=["cantidad"])
            else:
                CarritoItem.objects.create(
                    carrito=cart,
                    producto=product,
                    variante=variant,
                    talla=size,
                    cantidad=quantity,
                    precio_unitario=product.precio,
                )
        return

    cart = _session_cart(request)
    existing = cart.get(key, {}).get("cantidad", 0)
    _validate(product, variant, size, quantity, existing)
    cart[key] = {
        "producto_id": product.pk,
        "variante_id": variant.pk if variant else None,
        "talla": size,
        "cantidad": existing + quantity,
        "precio_unitario": cart[key]["precio_unitario"] if existing else str(product.precio),
    }
    request.session[SESSION_CART_KEY] = cart


def get_cart_lines(request):
    if request.user.is_authenticated:
        cart = Carrito.objects.filter(user=request.user).first()
        if not cart:
            return []
        items = cart.items.select_related("producto", "variante").all()
        return [
            CartLine(
                key=f"db:{item.pk}",
                producto=item.producto,
                variante=item.variante,
                talla=item.talla,
                cantidad=item.cantidad,
                precio_unitario=item.precio_unitario,
            )
            for item in items
        ]

    stored = _session_cart(request)
    products = {
        product.pk: product
        for product in Producto.objects.activos()
        .select_related("categoria")
        .filter(pk__in={item["producto_id"] for item in stored.values()})
    }
    variants = {
        variant.pk: variant
        for variant in ProductoVariante.objects.filter(
            pk__in={item["variante_id"] for item in stored.values() if item["variante_id"]}
        )
    }
    lines = []
    for key, item in stored.items():
        product = products.get(item["producto_id"])
        variant = variants.get(item["variante_id"])
        if product is None or (item["variante_id"] and (variant is None or variant.producto_id != product.pk)):
            continue
        lines.append(
            CartLine(
                key=key,
                producto=product,
                variante=variant,
                talla=item["talla"],
                cantidad=item["cantidad"],
                precio_unitario=Decimal(item["precio_unitario"]),
            )
        )
    return lines


def get_cart_count(request):
    if request.user.is_authenticated:
        cart = Carrito.objects.filter(user=request.user).first()
        return cart.cantidad_total if cart else 0
    return sum(item["cantidad"] for item in _session_cart(request).values())


def update_item(request, key, quantity):
    if quantity < 1:
        raise CartValidationError("La cantidad debe ser al menos 1.")
    if request.user.is_authenticated:
        if not key.startswith("db:"):
            raise CartValidationError("Ese artículo no pertenece a tu carrito.")
        try:
            item_id = int(key[3:])
        except ValueError:
            raise CartValidationError("Ese artículo no pertenece a tu carrito.")
        with transaction.atomic():
            item = (
                CarritoItem.objects.select_for_update()
                .select_related("producto", "variante", "carrito")
                .filter(pk=item_id, carrito__user=request.user)
                .first()
            )
            if item is None:
                raise CartValidationError("No encontramos ese artículo en tu carrito.")
            _validate(item.producto, item.variante, item.talla, quantity)
            item.cantidad = quantity
            item.save(update_fields=["cantidad"])
        return

    cart = _session_cart(request)
    item = cart.get(key)
    if item is None:
        raise CartValidationError("No encontramos ese artículo en tu carrito.")
    product = Producto.objects.select_related("categoria").filter(
        pk=item["producto_id"], estado=Producto.Estado.ACTIVO
    ).first()
    variant = (
        ProductoVariante.objects.filter(pk=item["variante_id"], producto=product).first()
        if product and item["variante_id"]
        else None
    )
    if product is None or (item["variante_id"] and variant is None):
        raise CartValidationError("Este producto ya no está disponible.")
    _validate(product, variant, item["talla"], quantity)
    item["cantidad"] = quantity
    cart[key] = item
    request.session[SESSION_CART_KEY] = cart


def remove_item(request, key):
    if request.user.is_authenticated:
        if not key.startswith("db:"):
            raise CartValidationError("Ese artículo no pertenece a tu carrito.")
        try:
            item_id = int(key[3:])
        except ValueError:
            raise CartValidationError("Ese artículo no pertenece a tu carrito.")
        deleted, _ = CarritoItem.objects.filter(pk=item_id, carrito__user=request.user).delete()
        if not deleted:
            raise CartValidationError("No encontramos ese artículo en tu carrito.")
        return

    cart = _session_cart(request)
    if key not in cart:
        raise CartValidationError("No encontramos ese artículo en tu carrito.")
    del cart[key]
    request.session[SESSION_CART_KEY] = cart


def merge_session_cart(request, user):
    cart = _session_cart(request)
    if not cart:
        return

    skipped = 0
    with transaction.atomic():
        user_cart, _ = Carrito.objects.get_or_create(user=user)
        for item_data in cart.values():
            product = Producto.objects.select_for_update().filter(
                pk=item_data["producto_id"], estado=Producto.Estado.ACTIVO
            ).first()
            variant_id = item_data["variante_id"]
            variant = (
                ProductoVariante.objects.select_for_update().filter(
                    pk=variant_id, producto=product
                ).first()
                if product and variant_id
                else None
            )
            if product is None or (variant_id and variant is None):
                skipped += 1
                continue
            existing = CarritoItem.objects.select_for_update().filter(
                carrito=user_cart,
                producto=product,
                variante=variant,
                talla=item_data["talla"],
            ).first()
            already = existing.cantidad if existing else 0
            available = variant.stock_actual if variant else product.stock_actual
            quantity = min(item_data["cantidad"], max(0, available - already))
            if quantity < 1:
                skipped += 1
                continue
            try:
                _validate(product, variant, item_data["talla"], quantity, already)
            except CartValidationError:
                skipped += 1
                continue
            if quantity < item_data["cantidad"]:
                skipped += 1
            if existing:
                existing.cantidad += quantity
                existing.save(update_fields=["cantidad"])
            else:
                CarritoItem.objects.create(
                    carrito=user_cart,
                    producto=product,
                    variante=variant,
                    talla=item_data["talla"],
                    cantidad=quantity,
                    precio_unitario=item_data["precio_unitario"],
                )
    request.session.pop(SESSION_CART_KEY, None)
    if skipped:
        messages.warning(
            request,
            "Algunos productos del carrito de invitado no pudieron trasladarse por disponibilidad.",
        )
