from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.contrib.auth.views import PasswordResetConfirmView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from apps.core import ratelimit

from . import services
from .emails import enviar_recuperacion, enviar_verificacion
from .forms import CorreoForm, LoginForm, PerfilClaveForm, PerfilInfoForm, RegistroForm

User = get_user_model()

MSG_RECUPERACION = "Si ese correo existe, recibirás un enlace en breve."
MSG_REENVIO = "Si esa cuenta existe y aún falta verificarla, te enviamos un enlace nuevo."


def _destino(request, user=None) -> str:
    """?next= si es seguro; si no, según el rol."""
    siguiente = request.POST.get("next") or request.GET.get("next") or ""
    if siguiente and url_has_allowed_host_and_scheme(
        siguiente, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return siguiente
    user = user or request.user
    return settings.LOGIN_DESTINO_PERSONAL if user.es_personal else settings.LOGIN_DESTINO_CLIENTE


@never_cache
@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect(_destino(request))

    form = LoginForm(request.POST or None)
    correo_sin_verificar = ""
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"].strip().lower()
        clave = form.cleaned_data["password"]
        rl_clave = f"login:{email}:{ratelimit.ip_del_cliente(request)}"
        if ratelimit.superado(rl_clave, settings.LIMITE_LOGIN[0]):
            form.add_error(None, "Demasiados intentos. Espera unos minutos e inténtalo de nuevo.")
        else:
            user = User.objects.filter(email__iexact=email).first()
            if user is None:
                User().set_password(clave)  # mismo tiempo de respuesta exista o no la cuenta
            if user and user.check_password(clave):
                # Con la contraseña correcta ya se puede ser específico sin revelar nada a un extraño.
                if not user.is_active:
                    form.add_error(None, "Tu cuenta está inhabilitada. Contacta a un administrador.")
                elif not user.puede_iniciar_sesion:
                    form.add_error(None, "Aún no has verificado tu correo. Revisa tu bandeja de entrada o spam.")
                    correo_sin_verificar = user.email
                else:
                    autenticado = authenticate(request, email=email, password=clave)
                    if autenticado:
                        login(request, autenticado)
                        ratelimit.reiniciar(rl_clave)
                        return redirect(_destino(request, autenticado))
            else:
                ratelimit.permitir(rl_clave, *settings.LIMITE_LOGIN)
                form.add_error(None, "Credenciales incorrectas.")
    return render(request, "auth/login.html", {
        "form": form,
        "next": request.POST.get("next") or request.GET.get("next") or "",
        "correo_sin_verificar": correo_sin_verificar,
    })


@never_cache
@require_http_methods(["GET", "POST"])
def registro_view(request):
    if request.user.is_authenticated:
        return redirect(_destino(request))
    form = RegistroForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if not ratelimit.permitir(f"registro:{ratelimit.ip_del_cliente(request)}", *settings.LIMITE_CORREO_POR_IP):
            form.add_error(None, "Demasiados registros desde esta conexión. Inténtalo más tarde.")
        else:
            try:
                user = services.registrar_cliente(**form.cleaned_data)
            except services.CorreoYaRegistrado:
                form.add_error("email", "Ya existe una cuenta registrada con este correo electrónico.")
            else:
                if enviar_verificacion(user):
                    messages.success(request, "Registro exitoso. Te enviamos un correo para verificar tu cuenta.")
                else:
                    messages.warning(
                        request,
                        "Tu cuenta se creó, pero no pudimos enviar el correo de verificación. "
                        "Pide uno nuevo con «Reenviar correo de verificación».",
                    )
                return redirect("login")
    return render(request, "auth/register.html", {"form": form})


def verificar_correo_view(request, token):
    user = services.verificar_correo(token)
    if user:
        messages.success(request, "¡Cuenta verificada exitosamente! Ya puedes iniciar sesión.")
    else:
        messages.error(request, "El enlace de verificación es inválido o ha expirado.")
    return redirect("login")


@require_POST
def reenviar_verificacion_view(request):
    form = CorreoForm(request.POST)
    if form.is_valid():
        email = form.cleaned_data["email"].strip().lower()
        ip_ok = ratelimit.permitir(f"reenvio-ip:{ratelimit.ip_del_cliente(request)}", *settings.LIMITE_CORREO_POR_IP)
        mail_ok = ratelimit.permitir(f"reenvio:{email}", *settings.LIMITE_CORREO_POR_DIRECCION)
        user = User.objects.filter(email__iexact=email, is_active=True).first() if ip_ok and mail_ok else None
        if user and (not user.email_verified or user.pending_email):
            destino = user.pending_email or user.email
            user.generar_token_verificacion()
            user.save(update_fields=["email_token", "email_token_expires_at", "updated_at"])
            enviar_verificacion(user, destino)
    messages.info(request, MSG_REENVIO)  # misma respuesta exista o no la cuenta
    return redirect("login")


@never_cache
@require_http_methods(["GET", "POST"])
def olvide_clave_view(request):
    form = CorreoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"].strip().lower()
        ip_ok = ratelimit.permitir(f"recup-ip:{ratelimit.ip_del_cliente(request)}", *settings.LIMITE_CORREO_POR_IP)
        mail_ok = ratelimit.permitir(f"recup:{email}", *settings.LIMITE_CORREO_POR_DIRECCION)
        if ip_ok and mail_ok:
            user = User.objects.filter(email__iexact=email, is_active=True).first()
            if user:
                enviar_recuperacion(user)
        messages.success(request, MSG_RECUPERACION)  # misma respuesta exista o no la cuenta
        return redirect("olvide_clave")
    return render(request, "auth/forgot_password.html", {"form": form})


class RestablecerClaveView(PasswordResetConfirmView):
    """El enlace se valida al abrirlo (no al enviar el formulario) y el token sale de la URL."""

    template_name = "auth/reset_password.html"
    success_url = reverse_lazy("login")
    post_reset_login = False

    def form_valid(self, form):
        messages.success(self.request, "¡Contraseña actualizada! Ya puedes iniciar sesión.")
        return super().form_valid(form)


# --------------------------------------------------------------------------- Mi cuenta
@login_required
@never_cache
def cuenta_view(request):
    return render(request, "account/index.html")


def _render_perfil(request, info_form=None, clave_form=None, status=200):
    return render(request, "account/profile.html", {
        "info_form": info_form or PerfilInfoForm(initial={"name": request.user.name, "email": request.user.email},
                                                 user=request.user),
        "clave_form": clave_form or PerfilClaveForm(user=request.user),
        "tiene_clave": request.user.has_usable_password(),
    }, status=status)


@login_required
@never_cache
def perfil_view(request):
    return _render_perfil(request)


@login_required
@require_POST
def perfil_info_view(request):
    form = PerfilInfoForm(request.POST, user=request.user)
    if not form.is_valid():
        return _render_perfil(request, info_form=form)
    user = request.user
    user.name = form.cleaned_data["name"].strip()
    user.save(update_fields=["name", "updated_at"])
    nuevo = form.cleaned_data["email"]
    if nuevo != user.email:
        services.solicitar_cambio_de_correo(user, nuevo)
        enviado = enviar_verificacion(user, nuevo)
        messages.success(
            request,
            "Te enviamos un enlace al nuevo correo. Seguirás entrando con el actual hasta confirmarlo."
            if enviado else
            "Guardamos tu nombre, pero no pudimos enviar el enlace al nuevo correo. Inténtalo de nuevo más tarde.",
            extra_tags="perfil",
        )
    else:
        messages.success(request, "Información de perfil actualizada.", extra_tags="perfil")
    return redirect("perfil")


@login_required
@require_POST
def perfil_clave_view(request):
    if not request.user.has_usable_password():
        messages.error(request, "Tu cuenta usa Google o Spotify. Para crear una contraseña usa «¿Olvidaste tu contraseña?».",
                       extra_tags="clave")
        return redirect("perfil")
    form = PerfilClaveForm(request.POST, user=request.user)
    if not form.is_valid():
        return _render_perfil(request, clave_form=form)
    request.user.set_password(form.cleaned_data["new_password"])
    request.user.save(update_fields=["password", "updated_at"])
    update_session_auth_hash(request, request.user)  # esta sesión sigue abierta; las demás se cierran
    messages.success(request, "Contraseña actualizada correctamente.", extra_tags="clave")
    return redirect("perfil")
