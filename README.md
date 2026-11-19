# STATELESS (Django)

Migración de STATELESS de Spring Boot a Django.
Incluye catálogo, carrito, checkout, pedidos, pagos con Mercado Pago, cuentas y panel de gestión.

## Mercado Pago (Checkout Pro con Preferences API)

La integración usa **Checkout Pro con Preferences API**, de acuerdo con la opción seleccionada en Mercado Pago. Se conecta a una venta existente y toma su monto de la base de datos. El SDK se instala junto con las demás dependencias siguiendo la sección **2. Instalación**.

**Aviso:** Mercado Pago muestra que Preferences API será descontinuada. Esta integración la conserva por ahora para coincidir con la opción seleccionada; revisa el aviso y su fecha en el panel, y planifica migrar a Orders API antes de que deje de estar disponible.

En `.env`, configura `MERCADOPAGO_ACCESS_TOKEN` con el Access Token del ambiente de prueba y `MERCADOPAGO_WEBHOOK_SECRET`
con la clave de firma del webhook. `MERCADOPAGO_PUBLIC_URL` debe ser la URL HTTPS pública de esta aplicación
para recibir notificaciones; en local puedes exponer el puerto `8081` con ngrok o cloudflared. No compartas
ni subas esos valores.

El recorrido web es: catálogo → carrito → iniciar sesión/checkout → pedido → botón **Pagar con Mercado Pago**.
El pago usa el total guardado en la base de datos, no importes enviados por el navegador. También se conserva
la API autenticada `POST /api/payments/` (JSON `{"venta_id": 123}`); consulta el estado con
`GET /api/payments/<reference>/`. Mercado Pago notifica cambios en `POST /api/payments/webhook/`.
El webhook confirma la venta solo después de consultar el pago real y verificar monto y moneda. Sin
`MERCADOPAGO_ACCESS_TOKEN`, puedes navegar y crear pedidos, pero no iniciar el pago.

Pruebas de pagos (desde la carpeta exterior): `& .\.venv\Scripts\python.exe .\stateless_pyyyy-main\manage.py test apps.payments`.

## 1. Base de datos

Django 5.2 **no funciona con el MariaDB 10.4 de XAMPP** (pide 10.5 o superior). Elige una opción:

- **Docker (recomendada):** abre Docker Desktop y ejecuta desde la carpeta exterior `docker compose -f .\stateless_pyyyy-main\docker-compose.yml up -d` (espera ~20 s). Levanta MySQL 8.4 en el puerto 3307.
  La clave de `.env` (`DB_PASSWORD`) debe coincidir con la de `docker-compose.yml`.
- **SQLite:** en el `.env` del proyecto pon `DB_ENGINE=sqlite`. No requiere un servidor de base de datos; Django crea o actualiza `db.sqlite3`.

## 2. Instalación (Windows, PowerShell)

En este ZIP el proyecto Django está dentro de otra carpeta. Si tu terminal muestra `PS C:\Users\Sanjo\Downloads\stateless_pyyyy-main>`, estás en la carpeta exterior; `requirements.txt` y `manage.py` están en `.\stateless_pyyyy-main\`. El entorno virtual `.venv` también está en la carpeta exterior.

Ejecuta estos comandos desde esa carpeta exterior:

```powershell
$proyecto = ".\stateless_pyyyy-main"
$python = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) { python -m venv .venv }
& $python -m pip install -r "$proyecto\requirements.txt"
if (-not (Test-Path "$proyecto\.env")) { Copy-Item "$proyecto\.env.example" "$proyecto\.env" }
notepad "$proyecto\.env"
```

En el `.env`, elige **una** base de datos de la sección 1. Para SQLite, cambia `DB_ENGINE=mysql` por `DB_ENGINE=sqlite`. Agrega también tus valores de Mercado Pago (`MERCADOPAGO_ACCESS_TOKEN`, `MERCADOPAGO_WEBHOOK_SECRET` y `MERCADOPAGO_PUBLIC_URL`). Guarda el archivo antes de migrar.

Luego ejecuta, también desde la carpeta exterior:

```powershell
& $python "$proyecto\manage.py" migrate
& $python "$proyecto\manage.py" crear_admin   # te pide tu correo real y tu contraseña
& $python "$proyecto\manage.py" cargar_demo   # opcional: 7 productos de demostración
& $python "$proyecto\manage.py" test apps.accounts apps.core apps.catalog apps.orders apps.cart apps.payments
& $python "$proyecto\manage.py" runserver 8081
```

Abre **http://127.0.0.1:8081** (usa siempre `127.0.0.1`, no `localhost`: Google y Spotify piden la dirección exacta).

En PowerShell, para ejecutar un `.exe` usando una ruta completa se usa el operador `&`, por ejemplo: `& 'C:\ruta\al\python.exe' -m pip ...`. No uses el formato Unix `/c:/...`.

Si la instalación de `mysqlclient` falla en Windows, comenta esa línea de `requirements.txt` y descomenta `PyMySQL`.

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
| `/essentials`, `/waves`, `/octane`, `/producto/<id>` | Colecciones y detalle de producto |
| `/carrito` | Agregar, actualizar y quitar productos; funciona para invitados y usuarios registrados |
| `/checkout` | Crear pedido y registrar dirección de envío (requiere iniciar sesión) |
| `/account/pedidos`, `/account/orders` | Lista de pedidos del usuario |
| `/account/pedidos/<id>` | Detalle del pedido y acceso al pago |
| `/admin/dashboard` | Resumen de pedidos (requiere una cuenta de personal) |
| `/logout` | Cerrar sesión (solo por POST) |
| `/django-admin/` | Panel nativo de Django (galería de imágenes, etc.) |

El checkout valida de nuevo el stock y el precio registrado en el carrito antes de crear la venta.

### Correos
Sin `EMAIL_HOST_USER` y `EMAIL_HOST_PASSWORD` en `.env`, los correos **se imprimen en la terminal** donde corre el servidor:
copia de ahí el enlace de verificación o de recuperación. Con las credenciales nuevas de Gmail (contraseña de aplicación), se envían de verdad.

### Entrar con Google
1. En Google Cloud Console crea unas credenciales OAuth **nuevas** (las anteriores quedaron expuestas).
2. Agrega esta **URI de redirección autorizada**: `http://127.0.0.1:8081/accounts/google/login/callback/`
3. Pon `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET` en `.env` y reinicia el servidor. El botón aparece solo.

## Si `migrate` dice "Can't connect to server" (error 10061)

No hay una base de datos corriendo: arranca Docker (sección 1) o pon `DB_ENGINE=sqlite` en `.env`.
