from django.contrib import admin

from .models import Payment, WebhookEvent


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("reference", "venta", "title", "status", "created_at")
    list_filter = ("status", "currency_id")
    search_fields = ("reference", "venta__id", "payer_email", "mp_payment_id", "preference_id")
    readonly_fields = ("reference", "raw_response", "created_at", "updated_at")


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ("received_at", "topic", "data_id", "signature_valid", "processed")
    list_filter = ("topic", "signature_valid", "processed")
    search_fields = ("data_id", "request_id")
    readonly_fields = [field.name for field in WebhookEvent._meta.fields]
