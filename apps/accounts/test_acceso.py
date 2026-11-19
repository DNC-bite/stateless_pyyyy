import re
from datetime import timedelta

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount, SocialLogin
from django.contrib.auth import get_user_model
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.core import mail
from django.core.cache import cache
from django.test import Client, RequestFactory, TestCase, override_settings
from django.utils import timezone

from apps.accounts.adapters import SocialAdapter
from apps.accounts.models import Role

User = get_user_model()
CLAVE = "Clave-segura-9"


def crear(email="ana@correo.com", verificado=True, **kw):
    return User.objects.create_user(email, CLAVE, name=kw.pop("name", "Ana"), email_verified=verificado, **kw)


def enlace_del_correo(msg):
    return re.search(r"https?://[^\s\"<]+", msg.body).group(0)


def ruta(url):
    return re.sub(r"^https?://[^/]+", "", url)


class AcceptTestCase(TestCase):
    def setUp(self):
        cache.clear()


class LoginTests(AcceptTestCase):
    def test_pagina_de_login(self):
        r = self.client.get("/login")
        self.assertContains(r, "INICIAR SESIÓN")
        self.assertNotContains(r, "Continuar con Google")  # sin claves de Google no se muestra el botón

    def test_login_correcto_va_a_cuenta(self):
        crear()
        r = self.client.post("/login", {"email": "ANA@correo.com", "password": CLAVE})
        self.assertRedirects(r, "/checkout", fetch_redirect_response=False)
        self.assertIn("_auth_user_id", self.client.session)

    def test_credenciales_incorrectas_mensaje_generico(self):
        crear()
        for correo, clave in (("ana@correo.com", "otra"), ("nadie@correo.com", CLAVE)):
            r = self.client.post("/login", {"email": correo, "password": clave})
            self.assertContains(r, "Credenciales incorrectas.")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_sin_verificar_solo_se_revela_con_la_clave_correcta(self):
        crear("nov@correo.com", verificado=False)
        r = self.client.post("/login", {"email": "nov@correo.com", "password": CLAVE})
        self.assertContains(r, "no has verificado tu correo")
        self.assertContains(r, "Reenviar correo de verificación")
        r = self.client.post("/login", {"email": "nov@correo.com", "password": "mal"})
        self.assertContains(r, "Credenciales incorrectas.")
        self.assertNotContains(r, "verificado")

    def test_cuenta_inhabilitada(self):
        crear("off@correo.com", is_active=False)
        r = self.client.post("/login", {"email": "off@correo.com", "password": CLAVE})
        self.assertContains(r, "inhabilitada")

    def test_next_seguro_se_respeta_y_externo_se_ignora(self):
        crear()
        r = self.client.post("/login", {"email": "ana@correo.com", "password": CLAVE, "next": "/checkout"})
        self.assertRedirects(r, "/checkout", fetch_redirect_response=False)
        self.client.logout()
        r = self.client.post("/login", {"email": "ana@correo.com", "password": CLAVE, "next": "https://malo.com/x"})
        self.assertRedirects(r, "/checkout", fetch_redirect_response=False)

    @override_settings(LIMITE_LOGIN=(3, 600))
    def test_limite_de_intentos(self):
        crear()
        for _ in range(3):
            self.client.post("/login", {"email": "ana@correo.com", "password": "mal"})
        r = self.client.post("/login", {"email": "ana@correo.com", "password": CLAVE})
        self.assertContains(r, "Demasiados intentos")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_ya_autenticado_no_ve_el_login(self):
        crear()
        self.client.post("/login", {"email": "ana@correo.com", "password": CLAVE})
        self.assertEqual(self.client.get("/login").status_code, 302)

    def test_cuenta_exige_login_y_conserva_next(self):
        r = self.client.get("/account")
        self.assertRedirects(r, "/login?next=/account", fetch_redirect_response=False)

    def test_logout_es_post_y_cierra_sesion(self):
        crear()
        self.client.post("/login", {"email": "ana@correo.com", "password": CLAVE})
        self.assertEqual(self.client.get("/logout").status_code, 405)
        self.client.post("/logout")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_el_backend_rechaza_no_verificados_en_todo_el_sistema(self):
        from django.contrib.auth import authenticate
        crear("nov@correo.com", verificado=False)
        self.assertIsNone(authenticate(email="nov@correo.com", password=CLAVE))

    def test_personal_y_cliente_van_a_su_destino(self):
        with override_settings(LOGIN_DESTINO_PERSONAL="/admin/dashboard", LOGIN_DESTINO_CLIENTE="/checkout"):
            crear("emp@correo.com", role=Role.objects.get(name="empleado"))
            r = self.client.post("/login", {"email": "emp@correo.com", "password": CLAVE})
            self.assertRedirects(r, "/admin/dashboard", fetch_redirect_response=False)
            self.client.logout()
            crear()
            r = self.client.post("/login", {"email": "ana@correo.com", "password": CLAVE})
            self.assertRedirects(r, "/checkout", fetch_redirect_response=False)


class RegistroYVerificacionTests(AcceptTestCase):
    def registrar(self, **extra):
        datos = {"name": "Luis", "email": "luis@correo.com", "password": CLAVE}
        datos.update(extra)
        return self.client.post("/register", datos)

    def test_registro_crea_cliente_sin_verificar_y_envia_correo(self):
        r = self.registrar()
        self.assertRedirects(r, "/login", fetch_redirect_response=False)
        u = User.objects.get(email="luis@correo.com")
        self.assertTrue(u.es_cliente and not u.email_verified and u.token_vigente())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(f"/auth/verificar/{u.email_token}", mail.outbox[0].body)
        self.assertIn("VERIFICAR MI CUENTA", mail.outbox[0].alternatives[0][0])

    def test_correo_repetido_en_cualquier_mayuscula(self):
        crear("luis@correo.com")
        r = self.registrar(email="LUIS@correo.com")
        self.assertContains(r, "Ya existe una cuenta registrada")
        self.assertEqual(User.objects.filter(email__iexact="luis@correo.com").count(), 1)

    def test_clave_debil_y_correo_invalido(self):
        self.assertContains(self.registrar(password="123"), "demasiado corta")
        self.assertContains(self.registrar(password="12345678"), "completamente numérica")
        self.assertContains(self.registrar(email="no-es-correo"), "correo")
        self.assertFalse(User.objects.filter(email="luis@correo.com").exists())

    def test_si_el_correo_falla_el_aviso_es_honesto(self):
        with override_settings(EMAIL_BACKEND="apps.accounts.test_acceso.CorreoRoto"):
            self.registrar()
            r = self.client.get("/login")
        self.assertContains(r, "no pudimos enviar el correo de verificación")
        self.assertTrue(User.objects.filter(email="luis@correo.com").exists())

    def test_verificar_y_entrar(self):
        self.registrar()
        u = User.objects.get(email="luis@correo.com")
        r = self.client.get(f"/auth/verificar/{u.email_token}")
        self.assertRedirects(r, "/login", fetch_redirect_response=False)
        u.refresh_from_db()
        self.assertTrue(u.email_verified)
        self.assertEqual(u.email_token, "")
        r = self.client.post("/login", {"email": "luis@correo.com", "password": CLAVE})
        self.assertRedirects(r, "/checkout", fetch_redirect_response=False)

    def test_enlace_invalido_o_vencido(self):
        self.registrar()
        u = User.objects.get(email="luis@correo.com")
        u.email_token_expires_at = timezone.now() - timedelta(minutes=1)
        u.save()
        r = self.client.get(f"/auth/verificar/{u.email_token}", follow=True)
        self.assertContains(r, "inválido o ha expirado")
        u.refresh_from_db()
        self.assertFalse(u.email_verified)
        self.assertContains(self.client.get("/auth/verificar/inventado", follow=True), "inválido o ha expirado")

    def test_reenvio_respuesta_igual_exista_o_no(self):
        crear("nov@correo.com", verificado=False)
        a = self.client.post("/auth/reenviar", {"email": "nov@correo.com"}, follow=True)
        n1 = len(mail.outbox)
        b = self.client.post("/auth/reenviar", {"email": "nadie@correo.com"}, follow=True)
        self.assertContains(a, "te enviamos un enlace nuevo")
        self.assertContains(b, "te enviamos un enlace nuevo")
        self.assertEqual((n1, len(mail.outbox)), (1, 1))  # solo se envió el de la cuenta real

    def test_reenvio_no_toca_cuentas_ya_verificadas(self):
        crear("ok@correo.com")
        self.client.post("/auth/reenviar", {"email": "ok@correo.com"})
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(LIMITE_CORREO_POR_DIRECCION=(2, 3600))
    def test_reenvio_limitado_por_direccion(self):
        crear("nov@correo.com", verificado=False)
        for _ in range(5):
            self.client.post("/auth/reenviar", {"email": "nov@correo.com"})
        self.assertEqual(len(mail.outbox), 2)


class CorreoRoto:
    """Backend de correo que siempre falla (para probar el mensaje honesto)."""

    def __init__(self, *a, **k):
        pass

    def send_messages(self, msgs):
        raise OSError("SMTP caído")

    def open(self):
        pass

    def close(self):
        pass


class RecuperarClaveTests(AcceptTestCase):
    def test_respuesta_igual_exista_o_no_y_solo_se_envia_a_cuentas_reales(self):
        crear()
        a = self.client.post("/forgot-password", {"email": "ana@correo.com"}, follow=True)
        b = self.client.post("/forgot-password", {"email": "nadie@correo.com"}, follow=True)
        self.assertContains(a, "Si ese correo existe")
        self.assertContains(b, "Si ese correo existe")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["ana@correo.com"])

    def test_flujo_completo_y_enlace_de_un_solo_uso(self):
        crear()
        self.client.post("/forgot-password", {"email": "ana@correo.com"})
        camino = ruta(enlace_del_correo(mail.outbox[0]))
        r = self.client.get(camino)  # el enlace se valida al abrirlo y el token sale de la URL
        self.assertEqual(r.status_code, 302)
        r = self.client.post(r.url, {"new_password1": "Nueva-clave-77", "new_password2": "Nueva-clave-77"})
        self.assertRedirects(r, "/login", fetch_redirect_response=False)
        r = self.client.post("/login", {"email": "ana@correo.com", "password": "Nueva-clave-77"})
        self.assertRedirects(r, "/checkout", fetch_redirect_response=False)
        self.client.logout()
        self.assertContains(Client().get(camino), "ENLACE NO VÁLIDO")  # ya usado

    def test_enlace_invalido(self):
        r = self.client.get("/reset-password/abc/enlace-falso/")
        self.assertContains(r, "ENLACE NO VÁLIDO")
        self.assertContains(r, "Solicita uno nuevo")

    def test_cuenta_inhabilitada_no_recibe_correo(self):
        crear(is_active=False)
        self.client.post("/forgot-password", {"email": "ana@correo.com"})
        self.assertEqual(len(mail.outbox), 0)

    def test_cuenta_de_google_puede_crear_su_primera_clave(self):
        u = User.objects.create(email="g@correo.com", name="G", email_verified=True,
                                role=Role.objects.get(name="cliente"))
        u.set_unusable_password()
        u.save()
        self.client.post("/forgot-password", {"email": "g@correo.com"})
        self.assertEqual(len(mail.outbox), 1)  # el formulario nativo de Django la habría ignorado

    def test_clave_nueva_debil_se_rechaza(self):
        crear()
        self.client.post("/forgot-password", {"email": "ana@correo.com"})
        r = self.client.get(ruta(enlace_del_correo(mail.outbox[0])))
        r = self.client.post(r.url, {"new_password1": "123", "new_password2": "123"})
        self.assertContains(r, "demasiado corta")


class PerfilTests(AcceptTestCase):
    def setUp(self):
        super().setUp()
        self.u = crear()
        self.client.post("/login", {"email": "ana@correo.com", "password": CLAVE})

    def test_pagina_de_perfil_y_cuenta(self):
        self.assertContains(self.client.get("/account/profile"), "DATOS PERSONALES")
        r = self.client.get("/account")
        self.assertContains(r, "MIS PEDIDOS")
        self.assertNotContains(r, "PANEL DE CONTROL")

    def test_personal_ve_el_panel_y_no_mis_pedidos(self):
        c = Client()
        crear("emp@correo.com", role=Role.objects.get(name="empleado"))
        c.post("/login", {"email": "emp@correo.com", "password": CLAVE})
        r = c.get("/account")
        self.assertContains(r, "PANEL DE CONTROL")
        self.assertNotContains(r, "MIS PEDIDOS")

    def test_cambiar_nombre(self):
        r = self.client.post("/account/profile/update-info", {"name": "Ana María", "email": "ana@correo.com"}, follow=True)
        self.assertContains(r, "Información de perfil actualizada.")
        self.u.refresh_from_db()
        self.assertEqual(self.u.name, "Ana María")
        self.assertEqual(len(mail.outbox), 0)

    def test_cambiar_correo_queda_pendiente_hasta_confirmar(self):
        r = self.client.post("/account/profile/update-info", {"name": "Ana", "email": "nuevo@correo.com"}, follow=True)
        self.assertContains(r, "Seguirás entrando con el actual")
        self.u.refresh_from_db()
        self.assertEqual((self.u.email, self.u.pending_email), ("ana@correo.com", "nuevo@correo.com"))
        self.assertEqual(mail.outbox[0].to, ["nuevo@correo.com"])
        self.client.get(ruta(enlace_del_correo(mail.outbox[0])))
        self.u.refresh_from_db()
        self.assertEqual((self.u.email, self.u.pending_email), ("nuevo@correo.com", ""))

    def test_correo_de_otra_cuenta_se_rechaza(self):
        crear("otra@correo.com")
        r = self.client.post("/account/profile/update-info", {"name": "Ana", "email": "OTRA@correo.com"})
        self.assertContains(r, "ya pertenece a otra cuenta")
        self.u.refresh_from_db()
        self.assertEqual(self.u.email, "ana@correo.com")

    def test_cambiar_clave_mantiene_la_sesion(self):
        r = self.client.post("/account/profile/update-password", {
            "current_password": CLAVE, "new_password": "Otra-clave-55", "new_password_confirmation": "Otra-clave-55"},
            follow=True)
        self.assertContains(r, "Contraseña actualizada correctamente.")
        self.assertEqual(self.client.get("/account").status_code, 200)  # sigue dentro
        self.u.refresh_from_db()
        self.assertTrue(self.u.check_password("Otra-clave-55"))

    def test_errores_de_clave(self):
        r = self.client.post("/account/profile/update-password", {
            "current_password": "mal", "new_password": "Otra-clave-55", "new_password_confirmation": "Otra-clave-55"})
        self.assertContains(r, "La contraseña actual es incorrecta.")
        r = self.client.post("/account/profile/update-password", {
            "current_password": CLAVE, "new_password": "Otra-clave-55", "new_password_confirmation": "distinta"})
        self.assertContains(r, "no coinciden")
        r = self.client.post("/account/profile/update-password", {
            "current_password": CLAVE, "new_password": "123", "new_password_confirmation": "123"})
        self.assertContains(r, "demasiado corta")

    def test_cuenta_social_no_muestra_formulario_de_clave(self):
        u = User.objects.create(email="g@correo.com", name="G", email_verified=True,
                                role=Role.objects.get(name="cliente"))
        u.set_unusable_password()
        u.save()
        c = Client()
        c.force_login(u)
        r = c.get("/account/profile")
        self.assertContains(r, "entra con Google o Spotify")
        self.assertNotContains(r, "ACTUALIZAR CONTRASEÑA")
        r = c.post("/account/profile/update-password", {"current_password": "x", "new_password": "y",
                                                         "new_password_confirmation": "y"}, follow=True)
        self.assertContains(r, "usa Google o Spotify")

    def test_los_posts_exigen_csrf(self):
        c = Client(enforce_csrf_checks=True)
        c.force_login(self.u)
        self.assertEqual(c.post("/account/profile/update-info", {"name": "X", "email": "x@x.co"}).status_code, 403)
        self.assertEqual(c.post("/logout").status_code, 403)


class SocialAdapterTests(AcceptTestCase):
    def request(self):
        req = RequestFactory().get("/")
        SessionMiddleware(lambda r: None).process_request(req)
        MessageMiddleware(lambda r: None).process_request(req)
        return req

    def sociallogin(self, email="g@gmail.com", verificado=True, uid="u1"):
        cuenta = SocialAccount(provider="google", uid=uid, extra_data={"email": email, "name": "Gina Pérez"})
        return SocialLogin(user=User(email=email), account=cuenta,
                           email_addresses=[EmailAddress(email=email, verified=verificado, primary=True)])

    def test_cuenta_nueva_de_google_es_cliente_verificada_y_sin_clave(self):
        adapter, req = SocialAdapter(), self.request()
        sl = self.sociallogin()
        adapter.populate_user(req, sl, {"email": "G@Gmail.com", "name": "Gina Pérez"})
        adapter.save_user(req, sl)
        u = User.objects.get(email="g@gmail.com")
        self.assertTrue(u.es_cliente and u.email_verified and not u.has_usable_password())
        self.assertEqual(u.name, "Gina Pérez")
        self.assertTrue(SocialAccount.objects.filter(user=u, provider="google").exists())

    def test_entra_a_la_cuenta_existente_con_el_mismo_correo_y_la_verifica(self):
        existente = crear("g@gmail.com", verificado=False)
        sl = self.sociallogin()
        SocialAdapter().pre_social_login(self.request(), sl)
        self.assertEqual(sl.user.pk, existente.pk)
        existente.refresh_from_db()
        self.assertTrue(existente.email_verified)

    def test_no_se_conecta_si_google_no_verifico_el_correo(self):
        existente = crear("g@gmail.com")
        sl = self.sociallogin(verificado=False)
        SocialAdapter().pre_social_login(self.request(), sl)
        self.assertIsNone(sl.user.pk)  # no se tomó la cuenta existente
        self.assertFalse(SocialAccount.objects.filter(user=existente).exists())

    def test_cuenta_inhabilitada_no_entra_con_google(self):
        from allauth.core.exceptions import ImmediateHttpResponse
        crear("g@gmail.com", is_active=False)
        with self.assertRaises(ImmediateHttpResponse) as cm:
            SocialAdapter().pre_social_login(self.request(), self.sociallogin())
        self.assertEqual(cm.exception.response.status_code, 302)

    def test_el_login_y_registro_propios_de_allauth_no_estan_expuestos(self):
        self.assertEqual(Client().get("/accounts/login/").status_code, 404)
        # /accounts/signup/ es el paso social de allauth: sin un login de Google en curso solo redirige.
        r = Client().get("/accounts/signup/")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(User.objects.count(), 0)

    @override_settings(GOOGLE_CLIENT_ID="id", GOOGLE_CLIENT_SECRET="secreto",
                       SOCIALACCOUNT_PROVIDERS={"google": {"APP": {"client_id": "id", "secret": "secreto", "key": ""},
                                                           "SCOPE": ["email", "profile"]}})
    def test_boton_de_google_solo_con_claves_y_por_post(self):
        r = self.client.get("/login")
        self.assertContains(r, "Continuar con Google")
        self.assertContains(r, 'action="/accounts/google/login/?process=login"')
        self.assertEqual(self.client.get("/accounts/google/login/").status_code, 200)  # pantalla de confirmación, no redirige
