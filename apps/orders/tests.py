from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.accounts.models import Role
from apps.catalog.models import Categoria, Producto, Proveedor
from apps.cart.models import Carrito, CarritoItem
from apps.orders.models import Envio, Venta

User = get_user_model()


def crear_venta(estado="pagado", total=250000):
    u, _ = User.objects.get_or_create(email="c@c.co", defaults={"name": "C"})
    return Venta.objects.create(usuario=u, metodo_pago="tarjeta_credito", total=total, estado=estado)


class VentaTests(TestCase):
    def test_numero_de_factura_y_desglose(self):
        v = crear_venta(total=Decimal("250000"))
        self.assertEqual(v.numero_factura, f"ST-{v.id:06d}")
        self.assertEqual((v.base_neta, v.iva), (Decimal("210084"), Decimal("39916")))


class EnvioPasoTests(TestCase):
    def paso(self, venta_estado, envio_estado):
        v = crear_venta(venta_estado)
        return Envio.objects.create(venta=v, direccion="Calle 1", ciudad="Bogotá", estado=envio_estado).paso_actual

    def test_pasos(self):
        self.assertEqual(self.paso("pendiente_pago", "pendiente"), 1)   # Efecty sin pagar: no está "confirmado"
        self.assertEqual(self.paso("pago_confirmado", "pendiente"), 2)
        self.assertEqual(self.paso("en_preparacion", "preparando"), 3)
        self.assertEqual(self.paso("enviado", "en_curso"), 4)
        self.assertEqual(self.paso("entregado", "entregado"), 5)


class StoreOrderViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "comprador@correo.com",
            "Clave-segura-123",
            name="Comprador",
            email_verified=True,
        )
        self.category = Categoria.objects.get(slug="essentials")
        self.provider, _ = Proveedor.objects.get_or_create(
            nombre="Proveedor de pedidos",
            defaults={
                "telefono": "123",
                "correo": "proveedor-pedidos@correo.com",
                "ciudad": "Bogotá",
            },
        )
        self.product = Producto.objects.create(
            nombre="Camiseta de pedido",
            precio="25000.00",
            stock_actual=5,
            categoria=self.category,
            proveedor=self.provider,
        )
        self.cart = Carrito.objects.create(user=self.user)
        self.item = CarritoItem.objects.create(
            carrito=self.cart,
            producto=self.product,
            talla="M",
            cantidad=2,
            precio_unitario="25000.00",
        )
        self.client.force_login(self.user)

    def test_checkout_creates_sale_shipping_and_clears_cart(self):
        response = self.client.post(
            "/checkout",
            {
                "destinatario": "Comprador",
                "telefono": "3001234567",
                "direccion": "Calle 10 # 5-20",
                "apartamento": "Apto 2",
                "ciudad": "Bogotá",
                "departamento": "Cundinamarca",
                "codigo_postal": "110111",
            },
        )

        sale = Venta.objects.get(usuario=self.user)
        self.assertRedirects(
            response,
            f"/account/pedidos/{sale.pk}",
            fetch_redirect_response=False,
        )
        self.assertEqual(sale.total, Decimal("50000.00"))
        self.assertEqual(sale.items.count(), 1)
        self.assertEqual(sale.envio.direccion, "Calle 10 # 5-20")
        self.assertFalse(self.cart.items.exists())
        self.assertEqual(self.client.get(f"/account/pedidos/{sale.pk}").status_code, 200)

    def test_checkout_rejects_insufficient_stock_without_creating_sale(self):
        self.product.stock_actual = 1
        self.product.save(update_fields=["stock_actual"])

        response = self.client.post(
            "/checkout",
            {
                "destinatario": "Comprador",
                "telefono": "3001234567",
                "direccion": "Calle 10 # 5-20",
                "ciudad": "Bogotá",
                "departamento": "Cundinamarca",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Solo quedan 1 unidad")
        self.assertFalse(Venta.objects.filter(usuario=self.user).exists())
        self.assertTrue(self.cart.items.filter(pk=self.item.pk).exists())

    def test_customer_cannot_open_another_users_order(self):
        other_user = User.objects.create_user(
            "otro-comprador@correo.com",
            "Clave-segura-123",
            name="Otro",
        )
        sale = Venta.objects.create(
            usuario=other_user,
            metodo_pago=Venta.Metodo.MERCADO_PAGO,
            total="10000.00",
        )

        response = self.client.get(f"/account/pedidos/{sale.pk}")

        self.assertEqual(response.status_code, 404)

    def test_order_list_and_dashboard_are_connected_with_role_checks(self):
        self.assertEqual(self.client.get("/account/orders").status_code, 200)
        self.assertEqual(self.client.get("/account/pedidos").status_code, 200)
        self.assertEqual(self.client.get("/account").status_code, 200)
        self.assertEqual(self.client.get("/admin/dashboard").status_code, 302)

    def test_staff_can_open_dashboard_and_old_order_without_shipping(self):
        employee_role, _ = Role.objects.get_or_create(name="empleado")
        employee = User.objects.create_user(
            "empleado@correo.com",
            "Clave-segura-123",
            name="Empleado",
            role=employee_role,
            email_verified=True,
        )
        sale = Venta.objects.create(
            usuario=employee,
            metodo_pago=Venta.Metodo.MERCADO_PAGO,
            total="10000.00",
        )
        self.client.force_login(employee)

        self.assertEqual(self.client.get("/account").status_code, 200)
        dashboard_response = self.client.get("/admin/dashboard")
        order_response = self.client.get(f"/account/pedidos/{sale.pk}")

        self.assertEqual(
            dashboard_response.status_code,
            200,
            dashboard_response.get("Location", ""),
        )
        self.assertContains(dashboard_response, sale.numero_factura)
        self.assertEqual(order_response.status_code, 200)
        self.assertContains(order_response, "No hay información de envío registrada.")

    @override_settings(DEBUG=True)
    @patch("apps.orders.views.payment_services.create_payment_preference")
    def test_pay_order_redirects_to_marketplace_sandbox(self, create_preference):
        sale = Venta.objects.create(
            usuario=self.user,
            metodo_pago=Venta.Metodo.MERCADO_PAGO,
            total="50000.00",
        )
        payment = SimpleNamespace(
            init_point="https://mercadopago.example/live",
            sandbox_init_point="https://mercadopago.example/sandbox",
        )
        create_preference.return_value = (payment, True)

        response = self.client.post(f"/account/pedidos/{sale.pk}/pagar")

        self.assertRedirects(
            response,
            "https://mercadopago.example/sandbox",
            fetch_redirect_response=False,
        )
