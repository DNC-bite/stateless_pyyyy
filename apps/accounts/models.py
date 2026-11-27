from datetime import timedelta

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone


class Role(models.Model):
    """Roles del sistema. Los tres primeros son los únicos con permisos definidos."""

    ADMIN = "admin"
    EMPLEADO = "empleado"
    CLIENTE = "cliente"
    BASE = (ADMIN, EMPLEADO, CLIENTE)

    name = models.CharField(
        "nombre", max_length=50, unique=True,
        validators=[RegexValidator(r"^[a-z0-9_]+$", "Solo minúsculas, números y guion bajo.")],
    )

    class Meta:
        ordering = ["id"]
        verbose_name = "rol"
        verbose_name_plural = "roles"

    def save(self, *args, **kwargs):
        self.name = (self.name or "").strip().lower()
        super().save(*args, **kwargs)

    @property
    def es_base(self) -> bool:
        return self.name in self.BASE

    def __str__(self):
        return self.name.upper()


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _crear(self, email, password, **extra):
        if not email:
            raise ValueError("El correo es obligatorio.")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_superuser", False)
        extra.setdefault("is_staff", False)
        if "role" not in extra and "role_id" not in extra:
            extra["role"], _ = Role.objects.get_or_create(name=Role.CLIENTE)
        return self._crear(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_superuser", True)
        extra.setdefault("is_staff", True)
        extra.setdefault("email_verified", True)
        if "role" not in extra and "role_id" not in extra:
            extra["role"], _ = Role.objects.get_or_create(name=Role.ADMIN)
        if not extra["is_superuser"] or not extra["is_staff"]:
            raise ValueError("Un superusuario debe tener is_staff e is_superuser en True.")
        return self._crear(email, password, **extra)

    def clientes(self):
        return self.filter(role__name=Role.CLIENTE)


class User(AbstractBaseUser, PermissionsMixin):
    class Estado(models.TextChoices):
        ACTIVO = "activo", "Activo"
        INACTIVO = "inactivo", "Inactivo"

    name = models.CharField("nombre", max_length=150)
    email = models.EmailField("correo", unique=True)
    # Campo real (Django lo usa en consultas, p. ej. al restablecer contraseñas). `estado` es su cara legible.
    is_active = models.BooleanField("activo", default=True)
    email_verified = models.BooleanField("correo verificado", default=False)
    email_token = models.CharField(max_length=64, blank=True, default="")
    email_token_expires_at = models.DateTimeField(null=True, blank=True)
    # Correo nuevo pendiente de verificar (el actual sigue valiendo hasta confirmarlo).
    pending_email = models.EmailField("correo pendiente", blank=True, default="")
    role = models.ForeignKey(Role, on_delete=models.PROTECT, null=True, blank=True, related_name="users")
    is_staff = models.BooleanField(default=False, help_text="Acceso a /django-admin/")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    class Meta:
        ordering = ["id"]
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"

    # --- Estado de la cuenta -------------------------------------------------
    @property
    def estado(self) -> str:
        return self.Estado.ACTIVO if self.is_active else self.Estado.INACTIVO

    @estado.setter
    def estado(self, valor):
        self.is_active = valor == self.Estado.ACTIVO

    @property
    def role_name(self) -> str:
        return self.role.name if self.role_id else ""

    @property
    def es_admin(self) -> bool:
        return self.is_superuser or self.role_name == Role.ADMIN

    @property
    def es_personal(self) -> bool:
        """Administrador o empleado: puede entrar al panel."""
        return self.es_admin or self.role_name == Role.EMPLEADO

    @property
    def es_cliente(self) -> bool:
        return self.role_name == Role.CLIENTE

    @property
    def puede_iniciar_sesion(self) -> bool:
        """Las cuentas de personal creadas por comando y los superusuarios no esperan verificación."""
        return self.is_active and (self.email_verified or self.is_superuser)

    @property
    def es_protegido(self) -> bool:
        """El superusuario no se puede suspender ni quitarle el rol desde el panel."""
        return self.is_superuser

    # --- Verificación de correo -----------------------------------------------
    def generar_token_verificacion(self) -> str:
        import secrets

        self.email_token = secrets.token_urlsafe(32)
        self.email_token_expires_at = timezone.now() + timedelta(hours=settings.EMAIL_VERIFICATION_HOURS)
        return self.email_token

    def token_vigente(self) -> bool:
        return bool(self.email_token) and self.email_token_expires_at is not None \
            and self.email_token_expires_at > timezone.now()

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        super().save(*args, **kwargs)

    def get_full_name(self):
        return self.name

    def get_short_name(self):
        return self.name.split(" ")[0] if self.name else self.email

    def __str__(self):
        return self.email
