from django.shortcuts import render


def home(request):
    # Provisional: la portada real (carrusel y Essentials) llega con el catálogo en la parte 3.
    return render(request, "home.html")
