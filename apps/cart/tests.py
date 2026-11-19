from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.catalog.models import Categoria, Producto, Proveedor

from .models import Carrito, CarritoItem


class CarritoViewTests(TestCase):
    def crear_producto(self, stock=10):
        category = Categoria.objects.get(slug="essentials")
        provider, _ = Proveedor.objects.get_or_create(
            nombre="Proveedor de prueba",
            defaults={
                "telefono": "123",
                "correo": "proveedor@correo.com",
                "ciudad": "Bogotá",
            },
        )
        return Producto.objects.create(
            nombre="Camiseta de prueba",
            precio="25000.00",
            stock_actual=stock,
            categoria=category,
            proveedor=provider,
        )

    def test_guest_can_open_empty_cart(self):
        response = self.client.get("/carrito")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "cart/cart.html")
        self.assertContains(response, "Tu carrito está vacío")

    def test_signed_in_user_sees_only_their_cart_items_and_total(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(
            "cliente@correo.com",
            "clave-segura-123",
            name="Cliente",
            email_verified=True,
        )
        other_user = user_model.objects.create_user("otro@correo.com", "clave-segura-123", name="Otro")
        category = Categoria.objects.get(slug="essentials")
        provider = Proveedor.objects.create(
            nombre="Proveedor de prueba",
            telefono="123",
            correo="proveedor@correo.com",
            ciudad="Bogotá",
        )
        product = Producto.objects.create(
            nombre="Camiseta STATELESS",
            precio="25000.00",
            categoria=category,
            proveedor=provider,
        )
        other_product = Producto.objects.create(
            nombre="Producto privado",
            precio="10000.00",
            categoria=category,
            proveedor=provider,
        )
        carrito = Carrito.objects.create(user=user)
        CarritoItem.objects.create(
            carrito=carrito,
            producto=product,
            cantidad=2,
            precio_unitario="25000.00",
        )
        other_cart = Carrito.objects.create(user=other_user)
        CarritoItem.objects.create(
            carrito=other_cart,
            producto=other_product,
            cantidad=1,
            precio_unitario="10000.00",
        )
        self.client.force_login(user)

        response = self.client.get("/carrito")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Camiseta STATELESS")
        self.assertNotContains(response, "Producto privado")
        self.assertEqual(response.context["cart_count"], 2)
        self.assertEqual(response.context["total"], Decimal("50000.00"))

    def test_guest_can_add_and_update_cart_item(self):
        product = self.crear_producto(stock=3)

        response = self.client.post(
            f"/carrito/agregar/{product.pk}",
            {"cantidad": "2", "talla": "M"},
        )

        self.assertRedirects(response, "/carrito", fetch_redirect_response=False)
        cart_response = self.client.get("/carrito")
        self.assertContains(cart_response, "Camiseta de prueba")
        self.assertEqual(cart_response.context["cart_count"], 2)
        self.assertEqual(cart_response.context["total"], Decimal("50000.00"))

        key = cart_response.context["items"][0].key
        response = self.client.post(
            "/carrito",
            {"action": "update", "key": key, "cantidad": "3"},
        )
        self.assertRedirects(response, "/carrito", fetch_redirect_response=False)
        self.assertEqual(self.client.get("/carrito").context["cart_count"], 3)

    def test_cart_rejects_quantity_above_stock_and_merges_on_login(self):
        product = self.crear_producto(stock=1)
        self.client.post(
            f"/carrito/agregar/{product.pk}",
            {"cantidad": "2", "talla": "M"},
        )
        self.assertEqual(self.client.get("/carrito").context["cart_count"], 0)

        self.client.post(
            f"/carrito/agregar/{product.pk}",
            {"cantidad": "1", "talla": "M"},
        )
        user = get_user_model().objects.create_user(
            "invitado@correo.com",
            "clave-segura-123",
            name="Invitado",
            email_verified=True,
        )
        self.client.force_login(user)

        response = self.client.get("/carrito")

        self.assertEqual(response.context["cart_count"], 1)
        self.assertTrue(Carrito.objects.filter(user=user).exists())
        self.assertNotIn("cart_items", self.client.session)

    def test_user_cannot_remove_another_users_cart_item(self):
        user_model = get_user_model()
        owner = user_model.objects.create_user("owner@correo.com", "clave-segura-123", name="Owner")
        visitor = user_model.objects.create_user("visitor@correo.com", "clave-segura-123", name="Visitor")
        product = self.crear_producto()
        owner_cart = Carrito.objects.create(user=owner)
        item = CarritoItem.objects.create(
            carrito=owner_cart,
            producto=product,
            cantidad=1,
            precio_unitario=product.precio,
        )
        self.client.force_login(visitor)

        self.client.post("/carrito", {"action": "remove", "key": f"db:{item.pk}"})

        self.assertTrue(CarritoItem.objects.filter(pk=item.pk).exists())
