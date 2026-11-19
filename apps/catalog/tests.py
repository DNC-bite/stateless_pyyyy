from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.catalog.models import Categoria, Producto, ProductoVariante, Proveedor
from io import StringIO


def crear_producto(nombre="Camisa", categoria="essentials", stock=10, minimo=5, **kw):
    prov, _ = Proveedor.objects.get_or_create(
        nombre="SA", defaults={"telefono": "1", "correo": "a@b.co", "ciudad": "Bogotá"})
    return Producto.objects.create(
        nombre=nombre, precio=1000, stock_actual=stock, stock_minimo=minimo,
        categoria=Categoria.objects.get(slug=categoria), proveedor=prov, **kw)


class CategoriaTests(TestCase):
    def test_colecciones_base_existen_y_estan_protegidas(self):
        self.assertEqual(Categoria.objects.filter(slug__in=Categoria.BASE_SLUGS).count(), 3)
        self.assertTrue(Categoria.objects.get(slug="waves").es_base)

    def test_slug_no_cambia_al_renombrar(self):
        c = Categoria.objects.create(nombre="Invierno 2026")
        self.assertEqual(c.slug, "invierno-2026")
        c.nombre = "Otoño"
        c.save()
        self.assertEqual(Categoria.objects.get(pk=c.pk).slug, "invierno-2026")
        self.assertFalse(c.es_base)

    def test_nombre_unico_sin_importar_mayusculas(self):
        with self.assertRaises(ValidationError):
            Categoria(nombre="WAVES").full_clean()


class StockTests(TestCase):
    def test_stock_total_suma_variantes(self):
        p = crear_producto(stock=10)
        ProductoVariante.objects.create(producto=p, color="Blanco", hex="#ffffff", stock_actual=5)
        ProductoVariante.objects.create(producto=p, color="Rojo", hex="#ff0000", stock_actual=3)
        self.assertEqual(Producto.objects.con_stock_total().get(pk=p.pk).stock_total, 18)
        self.assertEqual(Producto.objects.get(pk=p.pk).stock_total, 18)

    def test_estados_de_stock_y_tarjetas_no_se_duplican(self):
        agotado = crear_producto("A", stock=0)
        bajo = crear_producto("B", stock=3, minimo=5)
        justo = crear_producto("C", stock=5, minimo=5)
        bien = crear_producto("D", stock=50)
        self.assertEqual([agotado.estado_stock, bajo.estado_stock, justo.estado_stock, bien.estado_stock],
                         ["agotado", "bajo", "bajo", "disponible"])
        self.assertEqual(set(Producto.objects.sin_stock()), {agotado})
        self.assertEqual(set(Producto.objects.stock_bajo()), {bajo, justo})  # el agotado NO cuenta como "bajo"

    def test_variante_color_unico_por_producto(self):
        p = crear_producto()
        ProductoVariante.objects.create(producto=p, color="Negro", hex="#000000")
        with self.assertRaises(ValidationError):
            ProductoVariante(producto=p, color="negro", hex="#000000").full_clean()
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProductoVariante.objects.create(producto=p, color="Negro", hex="#111111")

    def test_hex_invalido(self):
        p = crear_producto()
        with self.assertRaises(ValidationError):
            ProductoVariante(producto=p, color="X", hex="rojo").full_clean()

    def test_stock_maximo_no_menor_que_minimo(self):
        p = crear_producto()
        p.stock_maximo = 2
        with self.assertRaises(ValidationError):
            p.full_clean()


class TallasTests(TestCase):
    def test_deteccion_automatica(self):
        self.assertEqual(crear_producto("Pantalón Negro").tipo_talla_efectivo, "pantalon")
        self.assertEqual(crear_producto("Jean Slim").tipo_talla_efectivo, "pantalon")
        self.assertEqual(crear_producto("Camisa Octane").tipo_talla_efectivo, "superior")
        # Igual que el sistema anterior: un "cargo" sin la palabra pantalón cae en superior...
        self.assertEqual(crear_producto("Cargo Oversize").tipo_talla_efectivo, "superior")

    def test_tipo_manual_gana(self):
        self.assertEqual(crear_producto("Cargo Oversize", tipo_talla="pantalon").tallas,
                         ["28", "30", "32", "34", "36"])
        gorra = crear_producto("Gorra", tipo_talla="unica")
        self.assertEqual(gorra.tallas, [])
        self.assertFalse(gorra.requiere_talla)


class DemoTests(TestCase):
    def test_cargar_demo_es_repetible(self):
        call_command("cargar_demo", stdout=StringIO())
        call_command("cargar_demo", stdout=StringIO())
        self.assertEqual(Producto.objects.count(), 7)
        self.assertEqual(Proveedor.objects.count(), 1)


class StorefrontViewTests(TestCase):
    def test_home_and_collection_link_to_product_detail(self):
        producto = crear_producto(nombre="Camiseta destacada")

        home = self.client.get("/")
        collection = self.client.get("/essentials")
        detail = self.client.get(f"/producto/{producto.pk}")

        self.assertEqual(home.status_code, 200)
        self.assertContains(home, "Camiseta destacada")
        self.assertEqual(collection.status_code, 200)
        self.assertContains(collection, f"/producto/{producto.pk}")
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "Agregar al carrito")

    def test_unknown_collection_returns_not_found(self):
        response = self.client.get("/coleccion-inexistente")
        self.assertEqual(response.status_code, 404)
