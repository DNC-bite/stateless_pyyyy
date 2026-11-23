from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("essentials", views.coleccion, {"slug": "essentials"}, name="essentials"),
    path("waves", views.coleccion, {"slug": "waves"}, name="waves"),
    path("octane", views.coleccion, {"slug": "octane"}, name="octane"),
    path("producto/<int:pk>", views.producto_detalle, name="producto"),
    path("producto/<int:pk>/recomendar", views.recomendar_view, name="recomendar_prendas"),
    path("catalogo", views.catalogo, name="catalogo"),
]
