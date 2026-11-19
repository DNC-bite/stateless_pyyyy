import uuid

from django.conf import settings
from django.db import models


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        APPROVED = "approved", "Aprobado"
        AUTHORIZED = "authorized", "Autorizado"
        IN_PROCESS = "in_process", "En proceso"
        IN_MEDIATION = "in_mediation", "En mediación"
        REJECTED = "rejected", "Rechazado"
        CANCELLED = "cancelled", "Cancelado"
        REFUNDED = "refunded", "Reembolsado"
        CHARGED_BACK = "charged_back", "Contracargo"

    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    venta = models.ForeignKey("orders.Venta", on_delete=models.PROTECT, related_name="pagos")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    currency_id = models.CharField(max_length=3, default="COP")
    payer_email = models.EmailField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    status_detail = models.CharField(max_length=100, blank=True)
    preference_id = models.CharField(max_length=100, blank=True, db_index=True)
    init_point = models.URLField(max_length=500, blank=True)
    sandbox_init_point = models.URLField(max_length=500, blank=True)
    mp_payment_id = models.CharField(max_length=50, blank=True, db_index=True)
    payment_method = models.CharField(max_length=50, blank=True)
    raw_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.reference} · {self.title} · {self.status}"

    @property
    def total_amount(self):
        return self.unit_price * self.quantity


class WebhookEvent(models.Model):
    request_id = models.CharField(max_length=100, blank=True, db_index=True)
    topic = models.CharField(max_length=50, blank=True)
    data_id = models.CharField(max_length=50, blank=True, db_index=True)
    payload = models.JSONField(default=dict)
    signature_valid = models.BooleanField(default=False)
    processed = models.BooleanField(default=False)
    error = models.TextField(blank=True)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-received_at"]

    def __str__(self):
        return f"{self.topic}:{self.data_id} ({'ok' if self.processed else 'pendiente'})"
