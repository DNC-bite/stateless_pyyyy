# STATELESS (Django)

Migración de STATELESS de Spring Boot a Django.
**Partes hechas:** 1 (base y modelos) · 2 (acceso y cuentas) · 3 (catálogo, carrito y checkout) · 4 (factura, pedidos y seguimiento) · 5 (panel administrativo).

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
python manage.py test          # debe terminar en OK (189 pruebas)
python manage.py runserver 8081
```

Abre **http://127.0.0.1:8081** (usa siempre `127.0.0.1`, no `localhost`: Google y Spotify piden la dirección exacta).

Si `pip install mysqlclient` falla en Windows, comenta esa línea de `requirements.txt` y descomenta `PyMySQL`.

## 3. Imágenes (importante)

Copia el contenido de `src/main/resources/static/images/` de tu proyecto Java a `static/images/`
**respetando los nombres exactamente** (Linux distingue mayúsculas). Sin ellas, las prendas de demostración
se ven con una imagen gris de respaldo.

Para registrar productos nuevos, abre `/admin/productos/nuevo` y arrastra una imagen al recuadro del formulario
(o selecciónala con un clic). La vista previa aparece antes de guardar; los archivos cargados se guardan en `media/productos/`
y se muestran en la tienda. Las imágenes ya existentes en `static/images/` siguen admitiendo su nombre de archivo.
De forma opcional, sube un modelo `.glb` en la edición de un producto: solo esa prenda mostrará el botón **Ver en 3D**.
El visor permite girar y acercar el modelo; los archivos pueden pesar hasta 50 MB.

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

## Si `migrate` dice "Can't connect to server" (error 10061)

No hay una base de datos corriendo: arranca Docker (sección 1) o pon `DB_ENGINE=sqlite` en `.env`.
