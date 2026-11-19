from django.test import TestCase

from apps.catalog.models import Categoria, Producto, ProductoVariante, Proveedor


def prov():
    return Proveedor.objects.get_or_create(nombre="SA", defaults={"telefono": "1", "correo": "a@b.co", "ciudad": "Bogotá"})[0]


def hacer(nombre, categoria="essentials", precio=100000, stock=10, **kw):
    return Producto.objects.create(nombre=nombre, precio=precio, stock_actual=stock, proveedor=prov(),
                                   categoria=Categoria.objects.get(slug=categoria), **kw)


class PortadaYColeccionesTests(TestCase):
    def test_portada_solo_muestra_essentials_activos(self):
        hacer("Camisa Visible")
        hacer("Camisa Oculta", estado="inactivo")
        hacer("Gorra Waves", categoria="waves")
        r = self.client.get("/")
        self.assertContains(r, "Camisa Visible")
        self.assertNotContains(r, "Camisa Oculta")
        self.assertNotContains(r, "Gorra Waves")
        self.assertContains(r, "STATELESS")

    def test_cada_coleccion_muestra_lo_suyo(self):
        hacer("Pieza E")
        hacer("Pieza W", categoria="waves")
        hacer("Pieza O", categoria="octane")
        for url, si, no in (("/essentials", "Pieza E", "Pieza W"), ("/waves", "Pieza W", "Pieza O"),
                            ("/octane", "Pieza O", "Pieza E")):
            r = self.client.get(url)
            self.assertContains(r, si)
            self.assertNotContains(r, no)

    def test_colecciones_vacias_no_rompen(self):
        for url in ("/", "/essentials", "/waves", "/octane", "/catalogo"):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_inactivos_no_aparecen_en_ninguna_coleccion(self):
        hacer("Fantasma", estado="inactivo", categoria="octane")
        self.assertNotContains(self.client.get("/octane"), "Fantasma")

    def test_agotado_se_marca_y_no_ofrece_compra(self):
        hacer("Sin Stock", stock=0)
        r = self.client.get("/essentials")
        self.assertContains(r, "AGOTADO")
        self.assertNotContains(r, "Elegir talla")

    def test_essentials_pide_talla_en_la_ficha_y_talla_unica_agrega_directo(self):
        p = hacer("Camisa")
        gorra = hacer("Gorra", tipo_talla="unica")
        r = self.client.get("/essentials")
        self.assertContains(r, f'href="/producto/{p.id}" class="btn-card-es">Elegir talla')
        self.assertContains(r, f'action="/carrito/agregar/{gorra.id}"')
        self.assertNotContains(r, f'action="/carrito/agregar/{p.id}"')

    def test_precio_con_formato_de_la_tienda(self):
        hacer("Cara", precio=250000)
        self.assertContains(self.client.get("/essentials"), "$250,000 COP")

    def test_una_variante_agotada_no_oculta_el_producto_con_stock(self):
        p = hacer("Mixto", stock=0)
        ProductoVariante.objects.create(producto=p, color="Rojo", hex="#ff0000", stock_actual=4)
        self.assertNotContains(self.client.get("/essentials"), "AGOTADO")


class FichaTests(TestCase):
    def test_ficha_de_camisa_trae_tallas_superiores(self):
        p = hacer("Camisa Octane")
        r = self.client.get(f"/producto/{p.id}")
        for t in ("S", "M", "L", "XL"):
            self.assertContains(r, f'data-talla="{t}"')
        self.assertNotContains(r, 'data-talla="28"')
        self.assertContains(r, 'data-requiere-talla="true"')

    def test_ficha_de_pantalon_trae_tallas_de_pantalon(self):
        p = hacer("Pantalón Negro")
        r = self.client.get(f"/producto/{p.id}")
        for t in ("28", "30", "32", "34", "36"):
            self.assertContains(r, f'data-talla="{t}"')
        self.assertNotContains(r, 'data-talla="XL"')

    def test_talla_unica_no_muestra_selector(self):
        p = hacer("Gorra", tipo_talla="unica")
        r = self.client.get(f"/producto/{p.id}")
        self.assertNotContains(r, "data-talla=")
        self.assertContains(r, 'data-requiere-talla="false"')

    def test_colores_con_su_existencia(self):
        p = hacer("Camisa", stock=3)
        v = ProductoVariante.objects.create(producto=p, color="Blanco", hex="#ffffff", stock_actual=0)
        r = self.client.get(f"/producto/{p.id}")
        self.assertContains(r, 'data-nombre="Original"')
        self.assertContains(r, f'data-id="{v.id}" data-nombre="Blanco"')
        self.assertContains(r, 'data-stock="0"')
        self.assertContains(r, "sin-stock")

    def test_producto_sin_variantes_no_muestra_selector_de_color(self):
        p = hacer("Camisa")
        self.assertNotContains(self.client.get(f"/producto/{p.id}"), 'id="color-nombre"')

    def test_inactivo_o_inexistente_da_404(self):
        p = hacer("Oculto", estado="inactivo")
        self.assertEqual(self.client.get(f"/producto/{p.id}").status_code, 404)
        self.assertEqual(self.client.get("/producto/99999").status_code, 404)

    def test_descripcion_por_defecto(self):
        p = hacer("Camisa")
        self.assertContains(self.client.get(f"/producto/{p.id}"), "Diseño exclusivo de la colección oficial STATELESS.")

    def test_imagen_de_respaldo_y_cloudinary(self):
        sin = hacer("Sin foto")
        self.assertContains(self.client.get(f"/producto/{sin.id}"), "placeholder.svg")
        con = hacer("Con foto", imagen="https://res.cloudinary.com/x/y.webp")
        self.assertContains(self.client.get(f"/producto/{con.id}"), 'src="https://res.cloudinary.com/x/y.webp"')
        local = hacer("Local", imagen="Cargo_Oversize_negro_esencial.jpg")
        self.assertContains(self.client.get(f"/producto/{local.id}"), "/static/images/Cargo_Oversize_negro_esencial.jpg")


class BuscadorTests(TestCase):
    def setUp(self):
        self.a = hacer("Camiseta Negra", precio=50000, descripcion="algodón pima")
        self.b = hacer("Gorra Roja", precio=150000, categoria="waves")
        self.c = hacer("Buso Agotado", precio=80000, stock=0)
        self.d = hacer("Oculto", estado="inactivo")

    def nombres(self, **params):
        r = self.client.get("/catalogo", params)
        return {p.nombre for p in r.context["productos"]}

    def test_sin_filtros_muestra_los_activos(self):
        self.assertEqual(self.nombres(), {"Camiseta Negra", "Gorra Roja", "Buso Agotado"})

    def test_palabra_clave_en_nombre_o_descripcion(self):
        self.assertEqual(self.nombres(q="gorra"), {"Gorra Roja"})
        self.assertEqual(self.nombres(q="PIMA"), {"Camiseta Negra"})

    def test_categoria_precio_y_disponibles(self):
        self.assertEqual(self.nombres(cat=self.b.categoria_id), {"Gorra Roja"})
        self.assertEqual(self.nombres(max="80000"), {"Camiseta Negra", "Buso Agotado"})
        self.assertEqual(self.nombres(disponible="true"), {"Camiseta Negra", "Gorra Roja"})
        self.assertEqual(self.nombres(max="100000", disponible="true", q="camiseta"), {"Camiseta Negra"})

    def test_valores_raros_no_rompen_la_pagina(self):
        r = self.client.get("/catalogo", {"max": "abc", "cat": "x", "q": "%"})
        self.assertEqual(r.status_code, 200)

    def test_formulario_conserva_lo_buscado_y_cuenta(self):
        r = self.client.get("/catalogo", {"q": "gorra", "disponible": "true"})
        self.assertContains(r, 'value="gorra"')
        self.assertContains(r, "checked")
        self.assertContains(r, "1 PRODUCTO ENCONTRADO")
        self.assertContains(self.client.get("/catalogo"), "3 PRODUCTOS ENCONTRADOS")

    def test_sin_resultados(self):
        r = self.client.get("/catalogo", {"q": "zzzz"})
        self.assertContains(r, "No se encontraron productos")
        self.assertContains(r, "LIMPIAR FILTROS")
