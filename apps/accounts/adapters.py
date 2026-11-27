from allauth.account.adapter import DefaultAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import redirect

from .models import Role

User = get_user_model()


class CuentaAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        return False  # las cuentas con correo se crean SOLO desde /register


class SocialAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(self, request, sociallogin):
        return True

    def _correo_verificado_por_proveedor(self, sociallogin):
        for ea in sociallogin.email_addresses:
            if ea.verified:
                return ea.email.strip().lower()
        return None

    def pre_social_login(self, request, sociallogin):
        """Si ya existe una cuenta con el correo que confirma Google, se entra a esa cuenta (como antes)."""
        if sociallogin.is_existing:
            return
        correo = self._correo_verificado_por_proveedor(sociallogin)
        if not correo:
            return
        existente = User.objects.filter(email__iexact=correo).first()
        if not existente:
            return
        if not existente.is_active:
            messages.error(request, "Tu cuenta está inhabilitada. Contacta a un administrador.")
            raise ImmediateHttpResponse(redirect("login"))
        if not existente.email_verified:  # el proveedor acaba de demostrar que el correo es suyo
            existente.email_verified = True
            existente.email_token, existente.email_token_expires_at = "", None
            existente.save(update_fields=["email_verified", "email_token", "email_token_expires_at", "updated_at"])
        sociallogin.connect(request, existente)

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        correo = (data.get("email") or user.email or "").strip().lower()
        nombre = data.get("name") or " ".join(filter(None, [data.get("first_name"), data.get("last_name")]))
        user.email = correo
        user.name = (nombre or correo.split("@")[0])[:150]
        user.email_verified = True
        user.role, _ = Role.objects.get_or_create(name=Role.CLIENTE)
        return user
