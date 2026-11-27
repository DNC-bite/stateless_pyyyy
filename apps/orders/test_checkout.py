import json
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, TestCase, override_settings

from apps.accounts.models import Role
from apps.accounts.test_acceso import CorreoRoto
from apps.cart.models import Carrito
from apps.catalog.models import Categoria, Producto, ProductoVariante, Proveedor
from apps.orders.models import Envio, Venta
from apps.payments.models import Payment

User = get_user_model()
CLAVE = "Clave-segura-9"

ENTREGA = {
    "nombre": "Ana", "apellidos": "Pérez", "direccion": "Carrera 11A # 93-93", "apartamento": "Torre 2 Apto 301",
    "ciudad": "Bogotá", "departamento": "Bogotá D.C.", "codigo_postal": "110111", "telefono": "3101234567",
    "metodo_pago": "tarjeta_credito",
}


def hacer(nombre="Camisa", precio=100000, stock=10, categoria="essentials", **kw):
    prov = Proveedor.objects.get_or_create(nombre="SA", defaults={"telefono": "1", "correo": "a@b.co", "ciudad": "B"})[0]
    return Producto.objects.create(nombre=nombre, precio=precio, stock_actual=stock, proveedor=prov,
                                   categoria=Categoria.objects.get(slug=categoria), **kw)


def cliente(email="ana@correo.com", role=None):
    kw = {"role": role} if role else {}
    return User.objects.create_user(email, CLAVE, name="Ana Pérez", email_verified=True, **kw)


def sesion(user):
    c = Client()
    c.force_login(user)
    return c


def llenar(c, p, talla="M", variante="", cantidad=1):
    c.post(f"/carrito/agregar/{p.id}", {"talla": talla, "varianteId": variante, "cantidad": cantidad})


def pagar(c, **cambios):
    datos = {**ENTREGA, **cambios}
    return c.post("/checkout/procesar", json.dumps(datos), content_type="application/json")


class PantallaDePagoTests(TestCase):
    def test_exige_sesion_y_vuelve_al_checkout(self):
        self.assertRedirects(self.client.get("/checkout"), "/login?next=/checkout", fetch_redirect_response=False)

    def test_bolsa_vacia_va_al_carrito(self):
        self.assertRedirects(sesion(cliente()).get("/checkout"), "/carrito", fetch_redirect_response=False)

    def test_muestra_resumen_sin_datos_de_otra_persona(self):
        c = sesion(cliente())
        p = hacer(precio=250000)
        llenar(c, p, "L", cantidad=2)
        r = c.get("/checkout")
        self.assertContains(r, "$ 500,000")           # total
        self.assertContains(r, "Talla L")
        self.assertContains(r, 'value="Ana"')          # nombre de la cuenta
        self.assertContains(r, 'value="Pérez"')
        self.assertContains(r, 'value="mercado_pago"')
        self.assertContains(r, 'id="confirmacionPago"')
        self.assertContains(r, 'id="confirmarPago"')
        self.assertContains(r, "js/checkout.js?v=checkout-confirmation-3")
        # Ningún dato de otra persona viene escrito en los campos (el ejemplo "Carrera 11A..." es solo texto de ayuda)
        for dato in ("Carrera 11A", "3101234567", "110111", "santiolivar", "Olivar"):
            self.assertNotContains(r, f'value="{dato}')
        self.assertContains(r, 'placeholder="Dirección exacta (ej. Carrera 11A # 93-93)"')
        self.assertContains(r, "Modo demostración")
        for depto in ("Amazonas", "Vichada", "Bogotá D.C."):
            self.assertContains(r, f'value="{depto}"')

    def test_desglose_de_iva(self):
        c = sesion(cliente())
        llenar(c, hacer(precio=250000))
        r = c.get("/checkout")
        self.assertContains(r, "$ 210,084")
        self.assertContains(r, "$ 39,916")

    def test_con_productos_agotados_vuelve_al_carrito(self):
        c = sesion(cliente())
        p = hacer(stock=2)
        llenar(c, p, cantidad=2)
        Producto.objects.filter(pk=p.pk).update(stock_actual=0)
        r = c.get("/checkout", follow=True)
        self.assertEqual(r.redirect_chain[-1][0], "/carrito")
        self.assertContains(r, "Revisa tu bolsa")

    def test_sugerencias_son_activas_con_stock_y_fuera_de_la_bolsa(self):
        c = sesion(cliente())
        en_bolsa = hacer("En Bolsa")
        hacer("Sugerida Uno"), hacer("Sugerida Dos")
        hacer("Sin Stock", stock=0), hacer("Oculta", estado="inactivo")
        llenar(c, en_bolsa)
        r = c.get("/checkout")
        nombres = {s.nombre for s in r.context["sugerencias"]}
        self.assertEqual(nombres, {"Sugerida Uno", "Sugerida Dos"})


class ProcesarPedidoTests(TestCase):
    def setUp(self):
        self.user = cliente()
        self.c = sesion(self.user)

    def test_compra_completa(self):
        p = hacer(precio=100000, stock=10)
        v = ProductoVariante.objects.create(producto=p, color="Blanco", hex="#ffffff", stock_actual=5)
        llenar(self.c, p, "M", cantidad=2)                 # color Original
        llenar(self.c, p, "L", variante=v.id, cantidad=3)  # color Blanco
        r = pagar(self.c)
        self.assertEqual(r.status_code, 200)

        venta = Venta.objects.get()
        self.assertEqual(r.json(), {"redirect": f"/checkout/confirmacion/{venta.id}"})
        self.assertEqual((venta.usuario, venta.total, venta.estado, venta.metodo_pago),
                         (self.user, 500000, "pago_confirmado", "tarjeta_credito"))
        self.assertEqual(venta.codigo_pago, "")
        self.assertEqual({(i.talla, i.variante_id, i.cantidad) for i in venta.items.all()},
                         {("M", None, 2), ("L", v.id, 3)})
        # Cada existencia baja por separado: el color Original y el color Blanco
        p.refresh_from_db(), v.refresh_from_db()
        self.assertEqual((p.stock_actual, v.stock_actual), (8, 2))
        # Envío con todos los datos del formulario (antes se perdían)
        e = venta.envio
        self.assertEqual((e.destinatario, e.telefono, e.direccion, e.apartamento, e.ciudad, e.departamento, e.codigo_postal),
                         ("Ana Pérez", "3101234567", "Carrera 11A # 93-93", "Torre 2 Apto 301", "Bogotá", "Bogotá D.C.", "110111"))
        self.assertEqual(e.estado, Envio.Estado.PENDIENTE)
        self.assertIsNotNone(e.fecha_confirmado)
        # La bolsa queda vacía y llega el correo
        self.assertFalse(Carrito.objects.get(user=self.user).items.exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(f"#{venta.id}", mail.outbox[0].body)
        self.assertIn("PAGO APROBADO", mail.outbox[0].body)
        self.assertIn("$500,000 COP", mail.outbox[0].body)

    def test_el_total_usa_los_precios_congelados_del_carrito(self):
        p = hacer(precio=100000)
        llenar(self.c, p)
        Producto.objects.filter(pk=p.pk).update(precio=999999)
        pagar(self.c)
        self.assertEqual(Venta.objects.get().total, 100000)

    def test_efecty_queda_pendiente_con_codigo_y_sin_fecha_de_confirmacion(self):
        llenar(self.c, hacer())
        pagar(self.c, metodo_pago="efecty")
        v = Venta.objects.get()
        self.assertEqual(v.estado, "pendiente_pago")
        self.assertRegex(v.codigo_pago, r"^EFY-[0-9A-F]{8}$")
        self.assertIsNone(v.envio.fecha_confirmado)
        self.assertIn("PENDIENTE DE PAGO", mail.outbox[0].body)
        self.assertNotIn("PAGO APROBADO", mail.outbox[0].body)

    def test_todos_los_metodos_validos(self):
        for metodo in ("tarjeta_credito", "paypal", "shop_pay", "google_pay", "nequi", "pse", "efecty"):
            llenar(self.c, hacer(f"P {metodo}"))
            self.assertEqual(pagar(self.c, metodo_pago=metodo).status_code, 200, metodo)
        self.assertEqual(Venta.objects.count(), 7)

    @override_settings(DEBUG=True, MERCADOPAGO_ACCESS_TOKEN="TEST-token")
    @patch("apps.payments.services.mercadopago.SDK")
    def test_mercado_pago_envia_al_sandbox_y_deja_pedido_pendiente(self, sdk_cls):
        sdk = MagicMock()
        sdk.preference.return_value.create.return_value = {
            "status": 201,
            "response": {
                "id": "pref-test-123",
                "init_point": "https://www.mercadopago.com/checkout/prod",
                "sandbox_init_point": "https://sandbox.mercadopago.com/checkout/test",
            },
        }
        sdk_cls.return_value = sdk
        llenar(self.c, hacer(precio=75000))

        response = pagar(self.c, metodo_pago=Venta.Metodo.MERCADO_PAGO)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"redirect": "https://sandbox.mercadopago.com/checkout/test"},
        )
        venta = Venta.objects.get()
        self.assertEqual(venta.estado, Venta.Estado.PENDIENTE_PAGO)
        self.assertIsNone(venta.envio.fecha_confirmado)
        self.assertEqual(Payment.objects.get(venta=venta).preference_id, "pref-test-123")
        self.assertIn("PENDIENTE DE PAGO", mail.outbox[0].body)
        self.assertNotIn("PAGO APROBADO", mail.outbox[0].body)

    @override_settings(DEBUG=True, MERCADOPAGO_ACCESS_TOKEN="TEST-token")
    @patch("apps.payments.services.mercadopago.SDK")
    def test_mercado_pago_no_redirige_a_produccion_si_falta_url_sandbox(self, sdk_cls):
        sdk = MagicMock()
        sdk.preference.return_value.create.return_value = {
            "status": 201,
            "response": {
                "id": "pref-test-123",
                "init_point": "https://www.mercadopago.com/checkout/prod",
            },
        }
        sdk_cls.return_value = sdk
        producto = hacer(stock=3)
        llenar(self.c, producto)

        response = pagar(self.c, metodo_pago=Venta.Metodo.MERCADO_PAGO)

        self.assertEqual(response.status_code, 502)
        self.assertIn("URL de pago de pruebas", response.json()["error"])
        self.assertEqual(Venta.objects.count(), 0)
        self.assertEqual(Payment.objects.count(), 0)
        self.assertEqual(Carrito.objects.get(user=self.user).items.count(), 1)
        producto.refresh_from_db()
        self.assertEqual(producto.stock_actual, 3)

    def test_sin_stock_no_cambia_nada(self):
        a, b = hacer("Hay", stock=5), hacer("Poco", stock=2)
        llenar(self.c, a, cantidad=3)
        llenar(self.c, b, cantidad=2)
        Producto.objects.filter(pk=b.pk).update(stock_actual=1)  # alguien más compró mientras tanto
        r = pagar(self.c)
        self.assertEqual(r.status_code, 409)
        self.assertIn("No hay stock suficiente de Poco. Disponible: 1.", r.json()["error"])
        a.refresh_from_db(), b.refresh_from_db()
        self.assertEqual((a.stock_actual, b.stock_actual), (5, 1))     # lo de "Hay" tampoco se descontó
        self.assertEqual(Venta.objects.count(), 0)
        self.assertEqual(Carrito.objects.get(user=self.user).items.count(), 2)  # la bolsa sigue intacta
        self.assertEqual(len(mail.outbox), 0)

    def test_dos_compradores_por_la_ultima_unidad_solo_uno_la_lleva(self):
        p = hacer(stock=1)
        otro = sesion(cliente("otro@correo.com"))
        llenar(self.c, p), llenar(otro, p)
        self.assertEqual(pagar(self.c).status_code, 200)
        self.assertEqual(pagar(otro).status_code, 409)
        p.refresh_from_db()
        self.assertEqual(p.stock_actual, 0)
        self.assertEqual(Venta.objects.count(), 1)

    def test_la_misma_prenda_en_dos_tallas_suma_la_demanda(self):
        p = hacer(stock=3)
        llenar(self.c, p, "M", cantidad=2)
        llenar(self.c, p, "L", cantidad=2)   # 4 > 3 aunque cada línea sola cabe
        self.assertEqual(pagar(self.c).status_code, 409)
        p.refresh_from_db()
        self.assertEqual(p.stock_actual, 3)

    def test_producto_desactivado_a_ultima_hora(self):
        p = hacer()
        llenar(self.c, p)
        Producto.objects.filter(pk=p.pk).update(estado="inactivo")
        r = pagar(self.c)
        self.assertEqual(r.status_code, 409)
        self.assertIn("ya no está disponible", r.json()["error"])

    def test_bolsa_vacia(self):
        r = pagar(self.c)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["redirect"], "/carrito")

    def test_datos_de_entrega_obligatorios_y_validados(self):
        llenar(self.c, hacer())
        for campo in ("nombre", "apellidos", "direccion", "ciudad", "departamento", "codigo_postal", "telefono"):
            r = pagar(self.c, **{campo: "  "})
            self.assertEqual(r.status_code, 400, campo)
            self.assertIn(campo, r.json()["campos"])
        self.assertEqual(Venta.objects.count(), 0)

    def test_departamento_telefono_y_metodo_invalidos(self):
        llenar(self.c, hacer())
        self.assertIn("departamento", pagar(self.c, departamento="Narnia").json()["campos"])
        self.assertIn("telefono", pagar(self.c, telefono="abc").json()["campos"])
        self.assertIn("metodo_pago", pagar(self.c, metodo_pago="bitcoin").json()["campos"])
        self.assertIn("metodo_pago", pagar(self.c, metodo_pago="tarjeta").json()["campos"])  # valor histórico, no se ofrece
        self.assertEqual(Venta.objects.count(), 0)

    def test_no_se_confia_en_precios_ni_totales_del_navegador(self):
        p = hacer(precio=100000)
        llenar(self.c, p)
        pagar(self.c, total=1, precio=1, items=[{"producto": p.id, "cantidad": 99}])
        v = Venta.objects.get()
        self.assertEqual((v.total, v.items.get().cantidad), (100000, 1))

    def test_json_invalido_y_metodo_no_post(self):
        self.assertEqual(self.c.post("/checkout/procesar", "no es json", content_type="application/json").status_code, 400)
        self.assertEqual(self.c.post("/checkout/procesar", "[1,2]", content_type="application/json").status_code, 400)
        self.assertEqual(self.c.get("/checkout/procesar").status_code, 405)

    def test_exige_sesion_y_csrf(self):
        self.assertEqual(Client().post("/checkout/procesar", "{}", content_type="application/json").status_code, 302)
        estricto = Client(enforce_csrf_checks=True)
        estricto.force_login(self.user)
        self.assertEqual(estricto.post("/checkout/procesar", json.dumps(ENTREGA), content_type="application/json").status_code, 403)

    @override_settings(EMAIL_BACKEND="apps.accounts.test_acceso.CorreoRoto")
    def test_si_el_correo_falla_la_compra_sigue_valida(self):
        llenar(self.c, hacer())
        self.assertEqual(pagar(self.c).status_code, 200)
        self.assertEqual(Venta.objects.count(), 1)

    def test_el_espacio_extra_se_limpia(self):
        llenar(self.c, hacer())
        pagar(self.c, direccion="  Calle   5   #  6-7 ", nombre="  Ana  ")
        e = Venta.objects.get().envio
        self.assertEqual((e.direccion, e.destinatario), ("Calle 5 # 6-7", "Ana Pérez"))


class ConfirmacionTests(TestCase):
    def setUp(self):
        self.dueno = cliente()
        self.c = sesion(self.dueno)
        llenar(self.c, hacer())
        pagar(self.c)
        self.venta = Venta.objects.get()
        self.url = f"/checkout/confirmacion/{self.venta.id}"

    def test_el_dueno_la_ve(self):
        r = self.c.get(self.url)
        self.assertContains(r, f"PEDIDO #{self.venta.id}")
        self.assertContains(r, "Pago Aprobado")
        self.assertContains(r, "Carrera 11A # 93-93")
        self.assertContains(r, "Recibe: Ana Pérez")
        self.assertContains(r, 'data-departamento="Bogotá D.C."')
        self.assertContains(r, "integrity=")   # Leaflet con verificación de integridad

    def test_otro_cliente_recibe_404_como_si_no_existiera(self):
        otro = sesion(cliente("otro@correo.com"))
        self.assertEqual(otro.get(self.url).status_code, 404)
        self.assertEqual(otro.get("/checkout/confirmacion/9999").status_code, 404)

    def test_el_personal_si_puede(self):
        for rol in ("admin", "empleado"):
            c = sesion(cliente(f"{rol}@correo.com", role=Role.objects.get(name=rol)))
            self.assertEqual(c.get(self.url).status_code, 200, rol)

    def test_sin_sesion_pide_login(self):
        self.assertEqual(Client().get(self.url).status_code, 302)

    def test_pedido_pendiente_de_pago(self):
        llenar(self.c, hacer("Otra"))
        pagar(self.c, metodo_pago="efecty")
        v = Venta.objects.get(metodo_pago="efecty")
        r = self.c.get(f"/checkout/confirmacion/{v.id}")
        self.assertContains(r, "Pendiente de pago")
        self.assertContains(r, v.codigo_pago)
        self.assertNotContains(r, "Pago Aprobado")
