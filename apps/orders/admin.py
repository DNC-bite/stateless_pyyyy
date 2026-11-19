from django.contrib import admin

from .models import Envio, GarantiaReclamo, Venta, VentaItem


class VentaItemInline(admin.TabularInline):
    model = VentaItem
    extra = 0


@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = ("id", "usuario", "metodo_pago", "total", "estado", "created_at")
    list_filter = ("estado", "metodo_pago")
    inlines = [VentaItemInline]


@admin.register(Envio)
class EnvioAdmin(admin.ModelAdmin):
    list_display = ("venta", "ciudad", "estado", "transportadora", "numero_guia")
    list_filter = ("estado",)


@admin.register(GarantiaReclamo)
class GarantiaAdmin(admin.ModelAdmin):
    list_display = ("id", "venta", "tipo_incidencia", "estado", "created_at")
    list_filter = ("estado", "tipo_incidencia")
