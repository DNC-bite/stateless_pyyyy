from django.urls import path

from . import views

urlpatterns = [
    path("carrito", views.carrito_view, name="carrito"),
    path("carrito/agregar/<int:pk>", views.agregar_view, name="carrito_agregar"),
    path("carrito/actualizar", views.actualizar_view, name="carrito_actualizar"),
    path("carrito/eliminar", views.eliminar_view, name="carrito_eliminar"),
]
