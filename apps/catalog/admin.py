from django.contrib import admin

from .models import Categoria, Producto, ProductoImagen, ProductoVariante, Proveedor


class ImagenInline(admin.TabularInline):
    model = ProductoImagen
    extra = 0


class VarianteInline(admin.TabularInline):
    model = ProductoVariante
    extra = 0


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "slug", "estado")
    readonly_fields = ("slug",)


@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ("nombre", "nit", "ciudad", "tipo_insumo", "estado")
    list_filter = ("estado", "tipo_insumo")
    search_fields = ("nombre", "nit", "ciudad")


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "categoria", "precio", "estado", "stock_actual", "stock_minimo")
    list_filter = ("estado", "categoria")
    search_fields = ("nombre",)
    inlines = [VarianteInline, ImagenInline]
