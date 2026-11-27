from io import StringIO

from django.contrib.auth import authenticate, get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.accounts.models import Role

User = get_user_model()


class RolesTests(TestCase):
    def test_roles_iniciales_existen(self):
        self.assertEqual(set(Role.objects.values_list("name", flat=True)), {"admin", "empleado", "cliente"})

    def test_rol_se_normaliza(self):
        r = Role.objects.create(name="  Auditor ")
        self.assertEqual(r.name, "auditor")
        self.assertFalse(r.es_base)


class UsuarioTests(TestCase):
    def test_create_user_es_cliente_y_correo_en_minusculas(self):
        u = User.objects.create_user("Ana@Correo.COM", "Clave-segura-9", name="Ana")
        self.assertEqual(u.email, "ana@correo.com")
        self.assertEqual(u.role.name, "cliente")
        self.assertTrue(u.es_cliente)
        self.assertFalse(u.es_personal)
        self.assertFalse(u.email_verified)

    def test_cliente_sin_verificar_no_puede_iniciar_sesion(self):
        u = User.objects.create_user("a@b.co", "Clave-segura-9", name="A")
        self.assertFalse(u.puede_iniciar_sesion)
        u.email_verified = True
        self.assertTrue(u.puede_iniciar_sesion)

    def test_cuenta_inactiva_no_se_autentica(self):
        u = User.objects.create_user("a@b.co", "Clave-segura-9", name="A", email_verified=True)
        self.assertIsNotNone(authenticate(email="a@b.co", password="Clave-segura-9"))
        u.estado = User.Estado.INACTIVO
        u.save()
        self.assertIsNone(authenticate(email="a@b.co", password="Clave-segura-9"))

    def test_correo_unico(self):
        User.objects.create_user("a@b.co", "x", name="A")
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user("a@b.co", "y", name="B")

    def test_superusuario_es_admin_protegido_y_verificado(self):
        u = User.objects.create_superuser("jefe@stateless.co", "Clave-segura-9", name="Jefe")
        self.assertTrue(u.es_admin and u.es_personal and u.es_protegido and u.email_verified)
        self.assertEqual(u.role.name, "admin")
        self.assertTrue(u.puede_iniciar_sesion)

    def test_token_de_verificacion(self):
        u = User.objects.create_user("a@b.co", "x", name="A")
        token = u.generar_token_verificacion()
        self.assertTrue(u.token_vigente())
        self.assertGreaterEqual(len(token), 32)


class CrearAdminTests(TestCase):
    def test_crea_administrador(self):
        out = StringIO()
        call_command("crear_admin", email="Yo@Mail.com", name="Yo", password="Clave-segura-9", stdout=out)
        u = User.objects.get(email="yo@mail.com")
        self.assertTrue(u.is_superuser and u.email_verified and u.es_admin)

    def test_actualiza_cuenta_existente(self):
        User.objects.create_user("yo@mail.com", "vieja-Clave-1", name="Antes")
        call_command("crear_admin", email="yo@mail.com", name="Nuevo", password="Clave-segura-9", stdout=StringIO())
        u = User.objects.get(email="yo@mail.com")
        self.assertTrue(u.is_superuser and u.check_password("Clave-segura-9"))
        self.assertEqual(u.name, "Nuevo")
        self.assertEqual(User.objects.count(), 1)

    def test_rechaza_clave_debil_y_correo_invalido(self):
        with self.assertRaises(CommandError):
            call_command("crear_admin", email="yo@mail.com", name="Yo", password="123", stdout=StringIO())
        with self.assertRaises(CommandError):
            call_command("crear_admin", email="no-es-correo", name="Yo", password="Clave-segura-9",
                         stdout=StringIO())
