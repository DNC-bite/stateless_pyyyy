from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.core.utils import desglose_iva


class Venta(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE_PAGO = "pendiente_pago", "Pendiente de pago"
        PAGO_CONFIRMADO = "pago_confirmado", "Pago confirmado"
        EN_PREPARACION = "en_preparacion", "En preparación"
        ENVIADO = "enviado", "Enviado"
        ENTREGADO = "entregado", "Entregado"
        CANCELADO = "cancelado", "Cancelado"

    class Metodo(models.TextChoices):
        TARJETA_CREDITO = "tarjeta_credito", "Tarjeta de crédito"
        PAYPAL = "paypal", "PayPal"
        SHOP_PAY = "shop_pay", "Shop Pay"
        GOOGLE_PAY = "google_pay", "Google Pay"
        EFECTY = "efecty", "Efecty"
        NEQUI = "nequi", "Nequi"
        PSE = "pse", "PSE"
        TARJETA = "tarjeta", "Tarjeta"  # valor histórico del sistema anterior

    class MotivoCancelacion(models.TextChoices):
        CLIENTE = "SOLICITUD_EXPRESA_CLIENTE", "Solicitud expresa del cliente (arrepentimiento / retracto)"
        GARANTIA = "DEFECTO_FABRICA_GARANTIA", "Prenda defectuosa / garantía textil (trasladar a proveedor)"
        INUBICABLE = "ERROR_DIRECCION_INUBICABLE", "Cliente inubicable / error de envío"
        STOCK = "QUIEBRE_STOCK", "Falta de stock o materia prima"

    # Estados desde los que el pedido todavía puede cancelarse o cambiarse.
    ESTADOS_ABIERTOS = (Estado.PENDIENTE_PAGO, Estado.PAGO_CONFIRMADO, Estado.EN_PREPARACION, Estado.ENVIADO)

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="ventas")
    tipo_venta = models.CharField(max_length=20, default="online")
    metodo_pago = models.CharField(max_length=20, choices=Metodo.choices)
    total = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])
    codigo_pago = models.CharField(max_length=30, blank=True, default="")
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDIENTE_PAGO)
    motivo_cancelacion = models.CharField(max_length=40, choices=MotivoCancelacion.choices, blank=True, default="")
    justificacion_cancelacion = models.TextField(blank=True, default="")
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "venta"
        verbose_name_plural = "ventas"

    @property
    def numero_factura(self) -> str:
        return f"ST-{self.id:06d}"

    @property
    def cancelada(self) -> bool:
        return self.estado == self.Estado.CANCELADO

    @property
    def base_neta(self) -> Decimal:
        return desglose_iva(self.total)[0]

    @property
    def iva(self) -> Decimal:
        return desglose_iva(self.total)[1]

    def __str__(self):
        return f"Venta #{self.id}"


class VentaItem(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name="items")
    producto = models.ForeignKey("catalog.Producto", on_delete=models.PROTECT, related_name="venta_items")
    variante = models.ForeignKey("catalog.ProductoVariante", on_delete=models.SET_NULL, null=True, blank=True)
    talla = models.CharField(max_length=10, blank=True, default="")
    cantidad = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ["id"]
        verbose_name = "ítem de venta"
        verbose_name_plural = "ítems de venta"

    @property
    def subtotal(self) -> Decimal:
        return self.precio_unitario * self.cantidad

    def __str__(self):
        return f"{self.producto} x{self.cantidad}"


class Envio(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        PREPARANDO = "preparando", "Preparando"
        EN_CURSO = "en_curso", "En camino"
        ENTREGADO = "entregado", "Entregado"
        CANCELADO = "cancelado", "Cancelado"

    class Transportadora(models.TextChoices):
        SERVIENTREGA = "Servientrega", "Servientrega"
        ENVIA = "Envía", "Envía"
        INTERRAPIDISIMO = "Interrapidisimo", "Interrapidísimo"
        DHL = "DHL", "DHL Express"

    venta = models.OneToOneField(Venta, on_delete=models.CASCADE, related_name="envio")
    destinatario = models.CharField(max_length=200, blank=True, default="")
    telefono = models.CharField(max_length=30, blank=True, default="")
    direccion = models.CharField(max_length=255)
    apartamento = models.CharField(max_length=120, blank=True, default="")
    ciudad = models.CharField(max_length=100)
    departamento = models.CharField(max_length=60, blank=True, default="")
    codigo_postal = models.CharField(max_length=12, blank=True, default="")
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.PENDIENTE)
    transportadora = models.CharField(max_length=30, choices=Transportadora.choices, blank=True, default="")
    numero_guia = models.CharField(max_length=60, blank=True, default="")
    fecha_confirmado = models.DateTimeField(null=True, blank=True)
    fecha_preparando = models.DateTimeField(null=True, blank=True)
    fecha_en_curso = models.DateTimeField(null=True, blank=True)
    fecha_entregado = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "envío"
        verbose_name_plural = "envíos"

    @property
    def paso_actual(self) -> int:
        """Paso del seguimiento del cliente: 1 pendiente · 2 confirmado · 3 en bodega · 4 en camino · 5 entregado."""
        venta_estado = self.venta.estado
        if self.estado == self.Estado.ENTREGADO:
            return 5
        if self.estado == self.Estado.EN_CURSO:
            return 4
        if self.estado == self.Estado.PREPARANDO:
            return 3
        if venta_estado in (Venta.Estado.PAGO_CONFIRMADO, Venta.Estado.EN_PREPARACION):
            return 2
        return 1

    def __str__(self):
        return f"Envío del pedido #{self.venta_id}"


class GarantiaReclamo(models.Model):
    class Tipo(models.TextChoices):
        PRENDA_DANADA = "PRENDA_DANADA", "Prenda Rota / Rasgada"
        COSTURA_ABIERTA = "COSTURA_ABIERTA", "Costura Suelta o Descosida"
        DEFECTO_TELA = "DEFECTO_TELA", "Defecto en Tela / Decoloración"
        TALLA_INCORRECTA = "TALLA_INCORRECTA", "Talla no corresponde a la etiqueta"
        CANCELACION = "CANCELACION_SOLICITADA", "Solicitud de Cancelación / Devolución"

    class Estado(models.TextChoices):
        RADICADO = "RADICADO", "Radicado"
        EN_AUDITORIA = "EN_AUDITORIA", "En auditoría"
        TRASLADADO = "TRASLADADO_A_PROVEEDOR", "Trasladado a proveedor"
        APROBADO = "APROBADO_GARANTIA", "Garantía aprobada"
        RECHAZADO = "RECHAZADO", "Rechazado"

    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name="garantias")
    producto = models.ForeignKey("catalog.Producto", on_delete=models.SET_NULL, null=True, blank=True)
    proveedor = models.ForeignKey("catalog.Proveedor", on_delete=models.SET_NULL, null=True, blank=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="garantias")
    tipo_incidencia = models.CharField(max_length=30, choices=Tipo.choices)
    descripcion_cliente = models.TextField()
    estado = models.CharField(max_length=30, choices=Estado.choices, default=Estado.RADICADO)
    respuesta_admin = models.TextField(blank=True, default="")
    notificado_proveedor = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "garantía / reclamo"
        verbose_name_plural = "garantías y reclamos"

    def __str__(self):
        return f"Reclamo #{self.id} · pedido #{self.venta_id}"
