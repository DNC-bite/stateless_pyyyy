from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test.utils import override_settings
from PIL import Image

from apps.accounts.models import Role
from apps.catalog.models import Categoria, Producto, ProductoImagen, ProductoVariante, Proveedor
from apps.dashboard.forms import MAX_TAMANO_MODELO_3D, ProductoForm
from apps.orders.models import Envio, GarantiaReclamo, Venta

User = get_user_model()


class PanelAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            "admin@example.com", "Clave-segura-9", name="Administradora"
        )
        self.cliente = User.objects.create_user(
            "cliente@example.com", "Clave-segura-9", name="Cliente", email_verified=True
        )
        self.categoria = Categoria.objects.get(slug="essentials")
        self.proveedor = Proveedor.objects.create(
            nombre="Proveedor Demo", telefono="3001234567", correo="proveedor@example.com", ciudad="Bogotá"
        )
        self.producto = Producto.objects.create(
            nombre="Camiseta", precio=100000, categoria=self.categoria, proveedor=self.proveedor,
            stock_actual=10, stock_minimo=3,
        )
        self.venta = Venta.objects.create(
            usuario=self.cliente, metodo_pago=Venta.Metodo.TARJETA_CREDITO, total=100000,
            estado=Venta.Estado.PAGO_CONFIRMADO,
        )
        self.envio = Envio.objects.create(
            venta=self.venta, destinatario="Cliente", telefono="3001234567", direccion="Calle 1",
            ciudad="Bogotá", departamento="Bogotá D.C.",
        )
        self.client.force_login(self.admin)

    def test_solo_personal_puede_abrir_el_panel(self):
        self.client.force_login(self.cliente)
        self.assertEqual(self.client.get("/admin/dashboard").status_code, 403)
        self.assertEqual(self.client.get("/admin/asistente").status_code, 403)
        self.assertEqual(self.client.get("/admin/reclamos").status_code, 403)

    @patch("apps.dashboard.views.responder_ollama", return_value="Hay un pedido confirmado.")
    def test_asistente_consulta_datos_actuales_sin_datos_personales(self, responder):
        response = self.client.post(
            "/admin/asistente/preguntar",
            data='{"question":"¿Cuántas ventas hay?"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer"], "Hay un pedido confirmado.")
        prompt = responder.call_args[0][0][-1]["content"]
        self.assertIn("resumen_ventas_pagadas", prompt)
        self.assertIn("Camiseta", prompt)
        instrucciones = responder.call_args[0][0][0]["content"]
        self.assertIn("punto para miles y coma para decimales", instrucciones)
        self.assertIn("Nunca uses coma como separador de miles", instrucciones)
        self.assertNotIn(self.cliente.email, prompt)
        self.assertNotIn(self.cliente.name, prompt)

    def test_asistente_rechaza_pregunta_invalida(self):
        response = self.client.post(
            "/admin/asistente/preguntar",
            data='{"question":" "}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_personal_gestiona_y_responde_reclamos(self):
        reclamo = GarantiaReclamo.objects.create(
            usuario=self.cliente, venta=self.venta, producto=self.producto,
            tipo_incidencia=GarantiaReclamo.Tipo.PRENDA_DANADA,
            descripcion_cliente="La tela llegó rasgada.",
        )
        self.assertContains(self.client.get("/admin/reclamos"), "La tela llegó rasgada.")
        response = self.client.post(
            f"/admin/reclamos/{reclamo.pk}/actualizar",
            {
                "estado": GarantiaReclamo.Estado.EN_AUDITORIA,
                "respuesta_admin": "Estamos revisando tu caso.",
            },
        )
        self.assertRedirects(response, "/admin/reclamos", fetch_redirect_response=False)
        reclamo.refresh_from_db()
        self.assertEqual(reclamo.estado, GarantiaReclamo.Estado.EN_AUDITORIA)
        self.assertEqual(reclamo.respuesta_admin, "Estamos revisando tu caso.")

    def test_cambios_de_venta_sincronizan_el_envio(self):
        response = self.client.post(
            f"/admin/ventas/{self.venta.pk}/estado",
            {"estado": Venta.Estado.EN_PREPARACION},
        )
        self.assertRedirects(response, "/admin/ventas", fetch_redirect_response=False)
        self.venta.refresh_from_db()
        self.envio.refresh_from_db()
        self.assertEqual(self.venta.estado, Venta.Estado.EN_PREPARACION)
        self.assertEqual(self.envio.estado, Envio.Estado.PREPARANDO)
        self.assertIsNotNone(self.envio.fecha_preparando)

    def test_modelo_3d_acepta_hasta_150_mb_y_rechaza_mas(self):
        form = ProductoForm()
        form.cleaned_data = {"modelo_3d_archivo": SimpleNamespace(size=MAX_TAMANO_MODELO_3D)}
        self.assertIsNotNone(form.clean_modelo_3d_archivo())

        form.cleaned_data["modelo_3d_archivo"].size += 1
        with self.assertRaises(ValidationError):
            form.clean_modelo_3d_archivo()

    def test_envio_en_camino_exige_transportadora_y_guia(self):
        response = self.client.post(
            f"/admin/envios/{self.envio.pk}/actualizar",
            {"estado": Envio.Estado.EN_CURSO, "transportadora": "", "numero_guia": ""},
        )
        self.assertRedirects(response, "/admin/envios", fetch_redirect_response=False)
        self.venta.refresh_from_db()
        self.assertEqual(self.venta.estado, Venta.Estado.PAGO_CONFIRMADO)
        self.assertEqual(self.envio.estado, Envio.Estado.PENDIENTE)

        self.client.post(
            f"/admin/envios/{self.envio.pk}/actualizar",
            {"estado": Envio.Estado.EN_CURSO, "transportadora": Envio.Transportadora.DHL, "numero_guia": "GUIA-123"},
        )
        self.venta.refresh_from_db()
        self.envio.refresh_from_db()
        self.assertEqual(self.venta.estado, Venta.Estado.ENVIADO)
        self.assertEqual(self.envio.numero_guia, "GUIA-123")

    def test_no_se_puede_eliminar_categoria_principal(self):
        response = self.client.post(f"/admin/categorias/{self.categoria.pk}/eliminar")
        self.assertRedirects(response, "/admin/categorias", fetch_redirect_response=False)
        self.assertTrue(Categoria.objects.filter(pk=self.categoria.pk).exists())

    def test_no_se_puede_eliminar_producto_con_ventas(self):
        from apps.orders.models import VentaItem

        VentaItem.objects.create(venta=self.venta, producto=self.producto, cantidad=1, precio_unitario=100000)
        response = self.client.post(f"/admin/productos/{self.producto.pk}/eliminar")
        self.assertRedirects(response, "/admin/productos", fetch_redirect_response=False)
        self.assertTrue(Producto.objects.filter(pk=self.producto.pk).exists())

    def test_reporte_excel_respeta_rango_y_exporta(self):
        response = self.client.get("/admin/reportes/exportar")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertIn(b"PK", response.content[:2])

    def test_todas_las_vistas_principales_se_renderizan(self):
        rutas = (
            "/admin/dashboard",
            "/admin/asistente",
            "/admin/reclamos",
            "/admin/ventas",
            f"/admin/ventas/{self.venta.pk}",
            "/admin/usuarios",
            f"/admin/usuarios/{self.cliente.pk}/editar",
            "/admin/envios",
            "/admin/productos",
            "/admin/productos/nuevo",
            f"/admin/productos/{self.producto.pk}/editar",
            "/admin/proveedores",
            "/admin/proveedores/nuevo",
            f"/admin/proveedores/{self.proveedor.pk}/editar",
            "/admin/categorias",
            "/admin/categorias/nueva",
            f"/admin/categorias/{self.categoria.pk}/editar",
            "/admin/reportes",
        )
        for ruta in rutas:
            with self.subTest(ruta=ruta):
                self.assertEqual(self.client.get(ruta).status_code, 200)

    def test_reporte_suma_iva_por_venta_y_no_sobre_el_total_global(self):
        Venta.objects.create(
            usuario=self.cliente, metodo_pago=Venta.Metodo.TARJETA_CREDITO, total=2,
            estado=Venta.Estado.PAGO_CONFIRMADO,
        )
        response = self.client.get("/admin/reportes")
        self.assertEqual(response.context["base"], 84036)
        self.assertEqual(response.context["iva"], 15966)

    def test_crear_producto_desde_el_panel(self):
        response = self.client.post("/admin/productos/nuevo", {
            "nombre": "Producto nuevo",
            "descripcion": "Descripción",
            "precio": "120000",
            "estado": Producto.Estado.ACTIVO,
            "imagen": "",
            "stock_actual": "8",
            "stock_minimo": "2",
            "stock_maximo": "100",
            "tipo_talla": Producto.TipoTalla.AUTO,
            "categoria": str(self.categoria.pk),
            "proveedor": str(self.proveedor.pk),
            "variantes-TOTAL_FORMS": "0",
            "variantes-INITIAL_FORMS": "0",
            "variantes-MIN_NUM_FORMS": "0",
            "variantes-MAX_NUM_FORMS": "1000",
            "imagenes-TOTAL_FORMS": "0",
            "imagenes-INITIAL_FORMS": "0",
            "imagenes-MIN_NUM_FORMS": "0",
            "imagenes-MAX_NUM_FORMS": "1000",
        })
        self.assertRedirects(response, "/admin/productos", fetch_redirect_response=False)
        self.assertTrue(Producto.objects.filter(nombre="Producto nuevo").exists())

    def test_crear_producto_con_imagen_subida(self):
        imagen_bytes = BytesIO()
        Image.new("RGB", (2, 2), color="red").save(imagen_bytes, format="PNG")

        with TemporaryDirectory() as media_dir, override_settings(MEDIA_ROOT=media_dir):
            response = self.client.post("/admin/productos/nuevo", {
                "nombre": "Producto con foto",
                "descripcion": "Descripción",
                "precio": "120000",
                "estado": Producto.Estado.ACTIVO,
                "imagen": "",
                "imagen_archivo": SimpleUploadedFile(
                    "producto.png", imagen_bytes.getvalue(), content_type="image/png"
                ),
                "stock_actual": "8",
                "stock_minimo": "2",
                "stock_maximo": "100",
                "tipo_talla": Producto.TipoTalla.AUTO,
                "categoria": str(self.categoria.pk),
                "proveedor": str(self.proveedor.pk),
                "variantes-TOTAL_FORMS": "0",
                "variantes-INITIAL_FORMS": "0",
                "variantes-MIN_NUM_FORMS": "0",
                "variantes-MAX_NUM_FORMS": "1000",
                "imagenes-TOTAL_FORMS": "0",
                "imagenes-INITIAL_FORMS": "0",
                "imagenes-MIN_NUM_FORMS": "0",
                "imagenes-MAX_NUM_FORMS": "1000",
            })

            self.assertRedirects(response, "/admin/productos", fetch_redirect_response=False)
            producto = Producto.objects.get(nombre="Producto con foto")
            self.assertTrue(producto.imagen.startswith("/media/productos/"))
            archivo_guardado = producto.imagen.removeprefix("/media/")
            self.assertTrue(Path(media_dir, archivo_guardado).is_file())
            self.assertContains(self.client.get("/essentials"), producto.imagen)

    def test_crear_producto_con_modelo_3d_glb(self):
        contenido_modelo = b"modelo GLB de prueba"
        datos = {
            "nombre": "Producto 3D",
            "descripcion": "Descripción",
            "precio": "120000",
            "estado": Producto.Estado.ACTIVO,
            "imagen": "",
            "modelo_3d": "",
            "modelo_3d_archivo": SimpleUploadedFile(
                "producto.glb", contenido_modelo, content_type="model/gltf-binary"
            ),
            "stock_actual": "8",
            "stock_minimo": "2",
            "stock_maximo": "100",
            "tipo_talla": Producto.TipoTalla.AUTO,
            "categoria": str(self.categoria.pk),
            "proveedor": str(self.proveedor.pk),
            "variantes-TOTAL_FORMS": "0",
            "variantes-INITIAL_FORMS": "0",
            "variantes-MIN_NUM_FORMS": "0",
            "variantes-MAX_NUM_FORMS": "1000",
            "imagenes-TOTAL_FORMS": "0",
            "imagenes-INITIAL_FORMS": "0",
            "imagenes-MIN_NUM_FORMS": "0",
            "imagenes-MAX_NUM_FORMS": "1000",
        }

        with TemporaryDirectory() as media_dir, override_settings(MEDIA_ROOT=media_dir):
            response = self.client.post("/admin/productos/nuevo", datos)

            self.assertRedirects(response, "/admin/productos", fetch_redirect_response=False)
            producto = Producto.objects.get(nombre="Producto 3D")
            self.assertTrue(producto.modelo_3d.startswith("/media/productos/modelos_3d/"))
            ruta_archivo = producto.modelo_3d.removeprefix("/media/")
            self.assertEqual(Path(media_dir, ruta_archivo).read_bytes(), contenido_modelo)

    def test_formulario_producto_muestra_zona_de_arrastre_y_vista_previa(self):
        self.producto.imagen = "/media/productos/actual.png"
        self.producto.save(update_fields=["imagen"])
        response = self.client.get(f"/admin/productos/{self.producto.pk}/editar")
        self.assertContains(response, "data-image-upload")
        self.assertContains(response, "Arrastra una imagen aquí o haz clic para seleccionarla")
        self.assertContains(response, "admin-image-upload.js")
        self.assertContains(response, "/media/productos/actual.png")

    def test_subir_imagenes_a_variante_y_galeria(self):
        imagen_bytes = BytesIO()
        Image.new("RGB", (2, 2), color="blue").save(imagen_bytes, format="PNG")
        contenido = imagen_bytes.getvalue()

        with TemporaryDirectory() as media_dir, override_settings(MEDIA_ROOT=media_dir):
            response = self.client.post(f"/admin/productos/{self.producto.pk}/editar", {
                "nombre": self.producto.nombre,
                "descripcion": self.producto.descripcion,
                "precio": str(self.producto.precio),
                "estado": self.producto.estado,
                "imagen": self.producto.imagen,
                "stock_actual": str(self.producto.stock_actual),
                "stock_minimo": str(self.producto.stock_minimo),
                "stock_maximo": str(self.producto.stock_maximo),
                "tipo_talla": self.producto.tipo_talla,
                "categoria": str(self.categoria.pk),
                "proveedor": str(self.proveedor.pk),
                "variantes-TOTAL_FORMS": "1",
                "variantes-INITIAL_FORMS": "0",
                "variantes-MIN_NUM_FORMS": "0",
                "variantes-MAX_NUM_FORMS": "1000",
                "variantes-0-id": "",
                "variantes-0-color": "Azul",
                "variantes-0-hex": "#112233",
                "variantes-0-imagen": "",
                "variantes-0-stock_actual": "4",
                "imagenes-TOTAL_FORMS": "1",
                "imagenes-INITIAL_FORMS": "0",
                "imagenes-MIN_NUM_FORMS": "0",
                "imagenes-MAX_NUM_FORMS": "1000",
                "imagenes-0-id": "",
                "imagenes-0-imagen": "",
                "imagenes-0-orden": "1",
                "variantes-0-imagen_archivo": SimpleUploadedFile(
                    "variante.png", contenido, content_type="image/png"
                ),
                "imagenes-0-imagen_archivo": SimpleUploadedFile(
                    "galeria.png", contenido, content_type="image/png"
                ),
            })

            self.assertRedirects(response, "/admin/productos", fetch_redirect_response=False)
            variante = ProductoVariante.objects.get(producto=self.producto)
            imagen_galeria = ProductoImagen.objects.get(producto=self.producto)
            self.assertTrue(variante.imagen.startswith("/media/productos/"))
            self.assertTrue(imagen_galeria.imagen.startswith("/media/productos/"))
