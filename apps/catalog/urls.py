from django.urls import path

from . import views

urlpatterns = [
    path("producto/<int:product_id>", views.producto_detalle, name="producto"),
    path("<slug:slug>", views.coleccion, name="coleccion"),
]
