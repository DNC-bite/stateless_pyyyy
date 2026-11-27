from django.contrib.auth.backends import ModelBackend


class EmailBackend(ModelBackend):
    """
    Inicio de sesión por correo. Una cuenta solo puede autenticarse si está activa y, salvo los
    superusuarios, con el correo verificado. Se aplica en TODO el sistema (no solo en el formulario).
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        correo = kwargs.get("email") or username
        if correo:
            correo = correo.strip().lower()
        return super().authenticate(request, username=correo, password=password)

    def user_can_authenticate(self, user):
        return bool(user.is_active) and user.puede_iniciar_sesion
