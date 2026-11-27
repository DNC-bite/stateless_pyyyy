from django.urls import path

from . import views

urlpatterns = [
    path("checkout", views.checkout_view, name="checkout"),
    path("checkout/procesar", views.procesar_view, name="procesar_pedido"),
    path("checkout/confirmacion/<int:pk>", views.confirmacion_view, name="confirmacion"),
    path("checkout/factura/<int:pk>", views.factura_view, name="factura"),
    path("checkout/factura/<int:pk>/descargar", views.factura_pdf_view, name="factura_pdf"),
    path("account/pedidos", views.pedidos_view, name="pedidos"),
    path("account/orders", views.pedidos_garantias_view, name="pedidos_garantias"),
    path("account/tracking/<int:pk>", views.tracking_view, name="tracking"),
    path("account/garantias/radicar", views.garantia_radicar_view, name="garantia_radicar"),
]
