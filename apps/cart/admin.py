from django.contrib import admin

from .models import Carrito, CarritoItem


class ItemInline(admin.TabularInline):
    model = CarritoItem
    extra = 0


@admin.register(Carrito)
class CarritoAdmin(admin.ModelAdmin):
    list_display = ("user", "updated_at")
    inlines = [ItemInline]
