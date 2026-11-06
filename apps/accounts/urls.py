from django.contrib.auth.views import LogoutView
from django.urls import include, path

from . import views

urlpatterns = [
    path("login", views.login_view, name="login"),
    path("login", views.login_view, name="account_login"),      # allauth redirige a este nombre
    path("register", views.registro_view, name="register"),
    path("register", views.registro_view, name="account_signup"),
    path("logout", LogoutView.as_view(next_page="login"), name="logout"),
    path("auth/verificar/<str:token>", views.verificar_correo_view, name="verificar_email"),
    path("auth/reenviar", views.reenviar_verificacion_view, name="reenviar_verificacion"),
    path("forgot-password", views.olvide_clave_view, name="olvide_clave"),
    path("reset-password/<uidb64>/<token>/", views.RestablecerClaveView.as_view(), name="restablecer_clave"),
    path("account", views.cuenta_view, name="cuenta"),
    path("account/profile", views.perfil_view, name="perfil"),
    path("account/profile/update-info", views.perfil_info_view, name="perfil_info"),
    path("account/profile/update-password", views.perfil_clave_view, name="perfil_clave"),
    # Solo las pantallas sociales de allauth (Google). Su login/registro propios NO se exponen.
    path("accounts/", include("allauth.socialaccount.urls")),
    path("accounts/", include("allauth.socialaccount.providers.google.urls")),
]
