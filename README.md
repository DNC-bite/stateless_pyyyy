# STATELESS (Django)

Migración de STATELESS de Spring Boot a Django.
**Partes hechas:** 1 (base y modelos) · 2 (acceso y cuentas).

## 1. Base de datos

Django 5.2 **no funciona con el MariaDB 10.4 de XAMPP** (pide 10.5 o superior). Elige una opción:

- **Docker (recomendada):** abre Docker Desktop y ejecuta `docker compose up -d` (espera ~20 s). Levanta MySQL 8.4 en el puerto 3307.
  La clave de `.env` (`DB_PASSWORD`) debe coincidir con la de `docker-compose.yml`.
- **SQLite:** en `.env` pon `DB_ENGINE=sqlite`. No instala nada; crea el archivo `db.sqlite3`.

## 2. Instalación (Windows, PowerShell, dentro de esta carpeta)

Si PowerShell dice que "la ejecución de scripts está deshabilitada", ejecuta **una vez**:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Después, **uno por uno** (no pegues el bloque entero):

```powershell
python -m venv venv
venv\Scripts\activate          # debe aparecer (venv) al inicio de la línea
pip install -r requirements.txt
copy .env.example .env         # y edítalo (ver sección 1)
python manage.py migrate
python manage.py crear_admin   # te pide tu correo real y tu contraseña
python manage.py cargar_demo   # opcional: 7 productos de demostración
python manage.py test          # debe terminar en OK
python manage.py runserver 8081
```

Abre **http://127.0.0.1:8081** (usa siempre `127.0.0.1`, no `localhost`: Google y Spotify piden la dirección exacta).

Si `pip install mysqlclient` falla en Windows, comenta esa línea de `requirements.txt` y descomenta `PyMySQL`.

## 3. Imágenes

Copia el contenido de `src/main/resources/static/images/` de tu proyecto Java a `static/images/`
**respetando los nombres exactamente** (Linux distingue mayúsculas).

## Parte 2: lo que ya funciona

| Ruta | Qué es |
|---|---|
| `/login`, `/register` | Acceso y registro (con verificación de correo a 24 h) |
| `/auth/verificar/<token>`, `/auth/reenviar` | Verificar el correo y pedir un enlace nuevo |
| `/forgot-password`, `/reset-password/...` | Recuperar la contraseña (enlace de 1 hora) |
| `/account`, `/account/profile` | Mi cuenta y perfil (nombre, correo, contraseña) |
| `/logout` | Cerrar sesión (solo por POST) |
| `/django-admin/` | Panel nativo de Django (galería de imágenes, etc.) |

Las rutas `/essentials`, `/carrito`, `/checkout`, `/admin/...`, `/account/orders` llegan en las partes 3 a 6.

### Correos
Sin `EMAIL_HOST_USER` y `EMAIL_HOST_PASSWORD` en `.env`, los correos **se imprimen en la terminal** donde corre el servidor:
copia de ahí el enlace de verificación o de recuperación. Con las credenciales nuevas de Gmail (contraseña de aplicación), se envían de verdad.

### Entrar con Google
1. En Google Cloud Console crea unas credenciales OAuth **nuevas** (las anteriores quedaron expuestas).
2. Agrega esta **URI de redirección autorizada**: `http://127.0.0.1:8081/accounts/google/login/callback/`
3. Pon `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET` en `.env` y reinicia el servidor. El botón aparece solo.

## Si `migrate` dice "Can't connect to server" (error 10061)

No hay una base de datos corriendo: arranca Docker (sección 1) o pon `DB_ENGINE=sqlite` en `.env`.
