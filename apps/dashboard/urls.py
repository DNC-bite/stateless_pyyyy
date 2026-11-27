from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("dashboard", views.inicio, name="inicio"),
    path("asistente", views.asistente, name="asistente"),
    path("asistente/preguntar", views.asistente_preguntar, name="asistente_preguntar"),
    path("reclamos", views.reclamos, name="reclamos"),
    path("reclamos/<int:pk>/actualizar", views.reclamo_actualizar, name="reclamo_actualizar"),
    path("ventas", views.ventas, name="ventas"),
    path("ventas/<int:pk>", views.venta_detalle, name="venta_detalle"),
    path("ventas/<int:pk>/estado", views.venta_estado, name="venta_estado"),
    path("usuarios", views.usuarios, name="usuarios"),
    path("usuarios/<int:pk>/editar", views.usuario_editar, name="usuario_editar"),
    path("usuarios/<int:pk>/estado", views.usuario_estado, name="usuario_estado"),
    path("envios", views.envios, name="envios"),
    path("envios/<int:pk>/actualizar", views.envio_actualizar, name="envio_actualizar"),
    path("productos", views.productos, name="productos"),
    path("productos/nuevo", views.producto_crear, name="producto_crear"),
    path("productos/<int:pk>/editar", views.producto_editar, name="producto_editar"),
    path("productos/<int:pk>/eliminar", views.producto_eliminar, name="producto_eliminar"),
    path("proveedores", views.proveedores, name="proveedores"),
    path("proveedores/nuevo", views.proveedor_crear, name="proveedor_crear"),
    path("proveedores/<int:pk>/editar", views.proveedor_editar, name="proveedor_editar"),
    path("proveedores/<int:pk>/eliminar", views.proveedor_eliminar, name="proveedor_eliminar"),
    path("categorias", views.categorias, name="categorias"),
    path("categorias/nueva", views.categoria_crear, name="categoria_crear"),
    path("categorias/<int:pk>/editar", views.categoria_editar, name="categoria_editar"),
    path("categorias/<int:pk>/eliminar", views.categoria_eliminar, name="categoria_eliminar"),
    path("reportes", views.reportes, name="reportes"),
    path("reportes/exportar", views.reporte_exportar, name="reporte_exportar"),
]
