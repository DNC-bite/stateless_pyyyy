import getpass

from django.contrib.auth import get_user_model
from django.db import connection
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email

from apps.accounts.models import Role


class Command(BaseCommand):
    help = (
        "Crea (o actualiza) la cuenta de administrador principal: superusuario, rol ADMIN y "
        "correo ya verificado. Reemplaza al correo fijo 'admin@example.com' del sistema anterior."
    )

    def add_arguments(self, parser):
        parser.add_argument("--email")
        parser.add_argument("--name")
        parser.add_argument("--password", help="Si no lo pasas, se pide por teclado (recomendado).")

    def handle(self, *args, **opts):
        connection.ensure_connection()  # si la base no responde, falla aquí y no después de pedirte los datos
        User = get_user_model()
        email = (opts["email"] or input("Correo del administrador: ")).strip().lower()
        try:
            validate_email(email)
        except ValidationError:
            raise CommandError("Ese correo no es válido.")
        name = (opts["name"] or input("Nombre completo: ")).strip() or "Administrador"

        password = opts["password"]
        if not password:
            password = getpass.getpass("Contraseña: ")
            if password != getpass.getpass("Repite la contraseña: "):
                raise CommandError("Las contraseñas no coinciden.")
        try:
            validate_password(password)
        except ValidationError as exc:
            raise CommandError(" ".join(exc.messages))

        role, _ = Role.objects.get_or_create(name=Role.ADMIN)
        user = User.objects.filter(email=email).first()
        if user:
            user.name, user.role = name, role
            user.is_superuser = user.is_staff = user.email_verified = True
            user.estado = User.Estado.ACTIVO
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Cuenta existente actualizada como administrador: {email}"))
        else:
            User.objects.create_superuser(email=email, password=password, name=name, role=role)
            self.stdout.write(self.style.SUCCESS(f"Administrador creado: {email}"))
