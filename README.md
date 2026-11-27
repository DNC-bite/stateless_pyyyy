# STATELESS (Django)

Migración de STATELESS de Spring Boot a Django.
**Partes hechas:** 1 (base y modelos) · 2 (acceso y cuentas) · 3 (catálogo, carrito y checkout) · 4 (factura, pedidos y seguimiento) · 5 (panel administrativo).
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

En desarrollo no se fija el correo del pagador en la preferencia, para que se pueda ingresar con un comprador
de prueba de Mercado Pago distinto de la cuenta vendedora.

Pruebas de pagos (desde la carpeta exterior): `& .\.venv\Scripts\python.exe .\stateless_pyyyy-main\manage.py test apps.payments`.

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
git clone <URL_DEL_REPOSITORIO>   # solo si todavía no has clonado el proyecto
cd <CARPETA_DEL_REPOSITORIO>
python -m venv venv
venv\Scripts\activate          # debe aparecer (venv) al inicio de la línea
pip install -r requirements.txt
copy .env.example .env         # y edítalo (ver sección 1)
```

`.env` es local y no se sube a Git. La plantilla usa SQLite y un modelo local liviano. Instala Ollama en el
computador nuevo, abre una terminal y descarga el modelo configurado:

```powershell
ollama pull qwen2.5:1.5b
```

Después ejecuta:

```powershell
python manage.py migrate
python manage.py crear_admin   # te pide tu correo real y tu contraseña
python manage.py cargar_demo   # opcional: 7 productos de demostración
python manage.py test          # debe terminar en OK (227 pruebas)
python manage.py runserver 8081
```

Abre **http://127.0.0.1:8081** (usa siempre `127.0.0.1`, no `localhost`: Google y Spotify piden la dirección exacta).
Si ya tenías una copia del repositorio en ese computador, en lugar de `git clone` ejecuta `git pull`.

Si `pip install mysqlclient` falla en Windows, comenta esa línea de `requirements.txt` y descomenta `PyMySQL`.

## 3. Imágenes (importante)

Copia el contenido de `src/main/resources/static/images/` de tu proyecto Java a `static/images/`
**respetando los nombres exactamente** (Linux distingue mayúsculas). Sin ellas, las prendas de demostración
se ven con una imagen gris de respaldo.

Para registrar productos nuevos, abre `/admin/productos/nuevo` y arrastra una imagen al recuadro del formulario
(o selecciónala con un clic). La vista previa aparece antes de guardar; los archivos cargados se guardan en `media/productos/`
y se muestran en la tienda. Las imágenes ya existentes en `static/images/` siguen admitiendo su nombre de archivo.
De forma opcional, sube un modelo `.glb` en la edición de un producto: solo esa prenda mostrará el botón **Ver en 3D**.
El visor permite girar y acercar el modelo; los archivos pueden pesar hasta 150 MB.
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
| `/logout` | Cerrar sesión (solo por POST) |
| `/django-admin/` | Panel nativo de Django (herramientas técnicas, galería de imágenes, etc.) |
| `/admin/dashboard` | Panel personalizado para administradores y empleados |

## Parte 3: la tienda

| Ruta | Qué es |
|---|---|
| `/` | Portada con el carrusel y los Essentials destacados |
| `/essentials`, `/waves`, `/octane` | Las tres colecciones |
| `/producto/<id>` | Ficha con colores y tallas |
| `/catalogo` | Catálogo con filtros (palabra clave, categoría, precio máximo, solo disponibles) |
| `/carrito` | Bolsa de compras (de invitado o de usuario; al iniciar sesión se unen) |
| `/checkout`, `/checkout/confirmacion/<id>` | Pago y confirmación del pedido (con mapa) |

**Probar una compra:** `python manage.py cargar_demo`, crea una cuenta en `/register` (el enlace de verificación sale en la
terminal), agrega una prenda, ve al carrito, paga con cualquier tarjeta de 16 dígitos. **El pago es una simulación**: no se
cobra nada y los datos de la tarjeta nunca salen del navegador.

## Parte 4: pedidos, factura y seguimiento

| Ruta | Qué es |
|---|---|
| `/checkout/factura/<id>` | Factura en pantalla (al imprimir sale en blanco y negro, legible) |
| `/checkout/factura/<id>/descargar` | La misma factura en PDF |
| `/account/pedidos` | Mis compras, con el botón de rastreo |
| `/account/orders` | Mis compras + centro de garantías (reportar una prenda dañada) |
| `/account/tracking/<id>` | Seguimiento del envío en 4 pasos |

Solo el dueño del pedido y el personal (admin y empleado) ven una factura, un seguimiento o una confirmación; para cualquier otra
persona es un 404. En el código, `apps/orders/services.py::cambiar_estado` es la **única** puerta para mover un pedido entre
estados: mantiene sincronizados el pedido y el envío, llena las fechas y avisa al cliente por correo. El panel de administración
(parte 5) la usará para cambiar estados y asignar guías.

**Los datos de la factura** (razón social, NIT, ciudad, correo de soporte y el subtítulo "Factura Oficial Electrónica") se cambian
en `.env` (`EMPRESA_*`, `FACTURA_SUBTITULO`). Una factura electrónica válida en Colombia exige un proveedor autorizado por la DIAN;
si el NIT no es real, cambia el subtítulo (por ejemplo a "Documento de Venta").

El panel `/admin/...` incluye inicio, ventas y cambios de estado, usuarios, logística, productos, proveedores,
categorías y reportes financieros con exportación a Excel. El acceso está limitado al personal; los cambios
de pedidos usan el servicio que sincroniza venta, envío y notificaciones.

## IA local y atención al cliente

La tienda incorpora recomendaciones de combinaciones en la ficha de cada producto y permite radicar quejas
generales o garantías desde `/account/orders`. El personal revisa y responde las solicitudes en
`/admin/reclamos`. El asistente `/admin/asistente` responde preguntas usando una consulta actualizada de
solo lectura sobre ventas, pedidos, inventario y reclamos; por privacidad, omite nombres, correos, direcciones
y descripciones privadas.

Ambas funciones usan Ollama local y no envían preguntas ni datos a una API externa. Instala Ollama, descarga
un modelo con capacidad de conversación (por ejemplo `ollama pull qwen2.5:14b`) y configura estas variables
en `.env`:

```env
OLLAMA_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5:14b
OLLAMA_NUM_CTX=32768
OLLAMA_TIMEOUT=120
```

`OLLAMA_NUM_CTX` define el máximo de contexto solicitado al modelo; el modelo y los recursos de la máquina
deben soportar ese tamaño. El asistente administrativo consulta la base de datos en cada pregunta, pero solo
expone agregados y listados acotados (hasta 200 productos, 30 pedidos y 30 reclamos recientes). Si Ollama no
está disponible, la aplicación muestra un error y no sustituye la respuesta con información inventada.
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
