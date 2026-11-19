"""
Configuración de STATELESS (Django).

Todo lo que cambia entre tu computador y producción se lee del archivo .env
(ver .env.example). Nunca escribas claves aquí.
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "si", "sí"}


# --------------------------------------------------------------------------
# Seguridad
# --------------------------------------------------------------------------
DEBUG = env_bool("DEBUG", True)

SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG:
        # Solo para desarrollo: clave fija y evidente. En producción es obligatoria.
        SECRET_KEY = "desarrollo-no-usar-en-produccion-" + "x" * 40
    else:
        raise RuntimeError("Falta SECRET_KEY en el archivo .env (obligatoria con DEBUG=False).")

ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") if h.strip()]
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8081").rstrip("/")
CSRF_TRUSTED_ORIGINS = [BASE_URL]

# --------------------------------------------------------------------------
# Aplicaciones
# --------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    # Login con Google / Spotify (solo la parte social; el login por correo es propio)
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    # Apps del proyecto
    "apps.core",
    "apps.accounts",
    "apps.catalog",
    "apps.cart",
    "apps.orders",
    "apps.reports",
    "apps.dashboard",
    "apps.player",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.tienda",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# --------------------------------------------------------------------------
# Base de datos  (MySQL de XAMPP por defecto; SQLite solo para pruebas)
# --------------------------------------------------------------------------
if os.getenv("DB_ENGINE", "mysql").lower() == "sqlite":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",  # con SQLite no se usa DB_NAME
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.getenv("DB_NAME", "stateless_db"),
            "USER": os.getenv("DB_USER", "root"),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", "127.0.0.1"),
            "PORT": os.getenv("DB_PORT", "3306"),
            "OPTIONS": {"charset": "utf8mb4"},
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------
# Usuarios y contraseñas
# --------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

if "test" in sys.argv:
    # Solo al ejecutar las pruebas: un cifrado rápido para que terminen en segundos.
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

PASSWORD_RESET_TIMEOUT = 60 * 60  # 1 hora, igual que el sistema anterior
EMAIL_VERIFICATION_HOURS = 24      # vigencia del enlace de verificación

AUTHENTICATION_BACKENDS = ["apps.accounts.backends.EmailBackend"]

LOGIN_URL = "/login"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login"
# A dónde va cada quien tras iniciar sesión (sin ?next=).
LOGIN_DESTINO_CLIENTE = "/checkout"
LOGIN_DESTINO_PERSONAL = "/admin/dashboard"

# Límites contra abuso (intentos por ventana de tiempo)
LIMITE_LOGIN = (10, 15 * 60)         # 10 intentos fallidos por correo+IP cada 15 min
LIMITE_CORREO_POR_DIRECCION = (3, 60 * 60)   # 3 correos (verificación / recuperación) por dirección y hora
LIMITE_CORREO_POR_IP = (10, 60 * 60)         # 10 por IP y hora

# --- allauth: solo se usa la parte "social"; no se crean cuentas por su registro propio ---
SITE_ID = 1
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_USER_MODEL_EMAIL_FIELD = "email"
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*"]
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_ADAPTER = "apps.accounts.adapters.CuentaAdapter"
SOCIALACCOUNT_ADAPTER = "apps.accounts.adapters.SocialAdapter"
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_LOGIN_ON_GET = False  # iniciar con Google exige un POST (con token CSRF)
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APP": {"client_id": GOOGLE_CLIENT_ID, "secret": GOOGLE_CLIENT_SECRET, "key": ""},
        "SCOPE": ["email", "profile"],
        "AUTH_PARAMS": {"access_type": "online"},
    },
}

# --------------------------------------------------------------------------
# Idioma, zona horaria y formatos
# --------------------------------------------------------------------------
LANGUAGE_CODE = "es-co"
TIME_ZONE = "America/Bogota"
USE_I18N = True
USE_TZ = True

# --------------------------------------------------------------------------
# Archivos estáticos
# --------------------------------------------------------------------------
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# --------------------------------------------------------------------------
# Datos fiscales (factura PDF / pantalla)  -- se cambian aquí, en un solo sitio
# --------------------------------------------------------------------------
EMPRESA_NOMBRE = os.getenv("EMPRESA_NOMBRE", "STATELESS CLOTHING S.A.S.")
EMPRESA_NIT = os.getenv("EMPRESA_NIT", "901.458.789-1")
EMPRESA_CIUDAD = os.getenv("EMPRESA_CIUDAD", "Bogotá D.C., Colombia")
EMPRESA_CORREO_SOPORTE = os.getenv("EMPRESA_CORREO_SOPORTE", "stateless2000@gmail.com")
# Texto bajo el nombre de la empresa en la factura. Si el NIT no es real, quita la palabra "Electrónica":
# una factura electrónica válida en Colombia exige un proveedor autorizado por la DIAN.
FACTURA_SUBTITULO = os.getenv("FACTURA_SUBTITULO", "Factura Oficial Electrónica")
IVA_PORCENTAJE = 19  # los precios ya incluyen IVA; la base se calcula total / 1.19

# Mientras no haya pasarela de pago real, el checkout es una simulación.
MODO_DEMO_PAGOS = env_bool("MODO_DEMO_PAGOS", True)

# --------------------------------------------------------------------------
# Correo
# --------------------------------------------------------------------------
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER or "stateless@localhost"
# Si no hay credenciales, los correos se imprimen en la consola en vez de enviarse.
EMAIL_BACKEND = (
    "django.core.mail.backends.smtp.EmailBackend"
    if EMAIL_HOST_USER and EMAIL_HOST_PASSWORD
    else "django.core.mail.backends.console.EmailBackend"
)
# Solo en desarrollo: redirige a este correo los avisos dirigidos a direcciones de prueba.
EMAIL_REDIRECT_TO = os.getenv("EMAIL_REDIRECT_TO", "") if DEBUG else ""

# --------------------------------------------------------------------------
# Cloudinary (credenciales opcionales; las cargas del panel se guardan en MEDIA_ROOT).
# --------------------------------------------------------------------------
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME", "")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY", "")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET", "")

# --------------------------------------------------------------------------
# Producción
# --------------------------------------------------------------------------
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
