from django.urls import path

from . import views

urlpatterns = [
    path("checkout", views.checkout, name="checkout"),
    path("account/pedidos", views.pedidos, name="pedidos"),
    path("account/orders", views.pedidos, name="orders_list"),
    path("account/pedidos/<int:order_id>", views.pedido_detalle, name="pedido_detalle"),
    path("account/orders/<int:order_id>", views.pedido_detalle, name="order_detail"),
    path("account/pedidos/<int:order_id>/pagar", views.pagar_pedido, name="pagar_pedido"),
    path("account/orders/<int:order_id>/pay", views.pagar_pedido, name="pay_order"),
    path("admin/dashboard", views.dashboard, name="dashboard"),
]
