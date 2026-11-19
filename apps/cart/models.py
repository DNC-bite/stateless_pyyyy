from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Carrito(models.Model):
    """Carrito de un usuario con sesión iniciada. El de invitado vive en la sesión del navegador."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="carrito")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "carrito"
        verbose_name_plural = "carritos"

    @property
    def total(self) -> Decimal:
        return sum((i.subtotal for i in self.items.all()), Decimal("0"))

    @property
    def cantidad_total(self) -> int:
        return sum(i.cantidad for i in self.items.all())

    def __str__(self):
        return f"Carrito de {self.user}"


class CarritoItem(models.Model):
    carrito = models.ForeignKey(Carrito, on_delete=models.CASCADE, related_name="items")
    producto = models.ForeignKey("catalog.Producto", on_delete=models.CASCADE)
    variante = models.ForeignKey("catalog.ProductoVariante", on_delete=models.CASCADE, null=True, blank=True)
    talla = models.CharField(max_length=10, blank=True, default="")
    cantidad = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    # El precio se congela al agregar al carrito (igual que el sistema anterior).
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ["id"]
        verbose_name = "ítem del carrito"
        verbose_name_plural = "ítems del carrito"

    @property
    def subtotal(self) -> Decimal:
        return self.precio_unitario * self.cantidad

    def __str__(self):
        return f"{self.producto} x{self.cantidad}"
