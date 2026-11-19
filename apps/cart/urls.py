from django.urls import path

from . import views

urlpatterns = [
    path("carrito", views.carrito_view, name="carrito"),
    path("carrito/agregar/<int:product_id>", views.agregar_carrito, name="agregar_carrito"),
]
