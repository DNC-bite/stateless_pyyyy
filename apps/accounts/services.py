from django.contrib.auth import get_user_model
from django.db import transaction

from .models import Role

User = get_user_model()


class CorreoYaRegistrado(Exception):
    pass


@transaction.atomic
def registrar_cliente(name: str, email: str, password: str):
    email = email.strip().lower()
    if User.objects.filter(email__iexact=email).exists():
        raise CorreoYaRegistrado
    rol, _ = Role.objects.get_or_create(name=Role.CLIENTE)
    user = User(name=name.strip(), email=email, role=rol, email_verified=False)
    user.set_password(password)
    user.generar_token_verificacion()
    user.save()
    return user


@transaction.atomic
def verificar_correo(token: str):
    """Confirma el correo (o el cambio de correo pendiente). Devuelve el usuario o None si el enlace no sirve."""
    if not token:
        return None
    user = User.objects.select_for_update().filter(email_token=token).first()
    if not user or not user.token_vigente():
        return None
    if user.pending_email:
        if User.objects.filter(email__iexact=user.pending_email).exclude(pk=user.pk).exists():
            return None  # alguien más tomó ese correo mientras tanto
        user.email, user.pending_email = user.pending_email, ""
    user.email_verified = True
    user.email_token, user.email_token_expires_at = "", None
    user.save()
    return user


@transaction.atomic
def solicitar_cambio_de_correo(user, nuevo: str):
    """El correo actual sigue valiendo hasta que se confirme el enlace enviado al nuevo."""
    user.pending_email = nuevo.strip().lower()
    user.generar_token_verificacion()
    user.save(update_fields=["pending_email", "email_token", "email_token_expires_at", "updated_at"])
    return user
