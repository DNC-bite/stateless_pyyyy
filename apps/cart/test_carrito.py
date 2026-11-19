from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from apps.cart.models import Carrito
from apps.cart.services import SESSION_KEY
from apps.catalog.models import Categoria, Producto, ProductoVariante, Proveedor

User = get_user_model()
CLAVE = "Clave-segura-9"


def hacer(nombre="Camisa", precio=100000, stock=10, categoria="essentials", **kw):
    prov = Proveedor.objects.get_or_create(nombre="SA", defaults={"telefono": "1", "correo": "a@b.co", "ciudad": "B"})[0]
    return Producto.objects.create(nombre=nombre, precio=precio, stock_actual=stock, proveedor=prov,
                                   categoria=Categoria.objects.get(slug=categoria), **kw)


def cliente(email="ana@correo.com"):
    return User.objects.create_user(email, CLAVE, name="Ana Pérez", email_verified=True)


def agregar(c, p, talla="M", variante="", cantidad=1):
    return c.post(f"/carrito/agregar/{p.id}", {"talla": talla, "varianteId": variante, "cantidad": cantidad})


def lineas(c):
    return c.get("/carrito").context["lineas"]


class CarritoInvitadoTests(TestCase):
    def test_agregar_y_ver(self):
        p = hacer()
        r = agregar(self.client, p)
        self.assertRedirects(r, "/carrito", fetch_redirect_response=False)
        (l,) = lineas(self.client)
        self.assertEqual((l.producto, l.talla, l.cantidad), (p, "M", 1))
        self.assertContains(self.client.get("/carrito"), "$100,000 COP")

    def test_carrito_vacio(self):
        r = self.client.get("/carrito")
        self.assertContains(r, "TU BOLSA ESTÁ VACÍA")
        self.assertNotContains(r, "PROCEDER AL PAGO")

    def test_exige_talla_y_vuelve_a_la_ficha_con_el_aviso(self):
        p = hacer()
        r = agregar(self.client, p, talla="")
        self.assertRedirects(r, f"/producto/{p.id}", fetch_redirect_response=False)
        self.assertContains(self.client.get(f"/producto/{p.id}"), "Selecciona una talla")
        self.assertEqual(lineas(self.client), [])

    def test_talla_invalida_para_el_producto(self):
        p = hacer("Camisa")  # superior: S M L XL
        agregar(self.client, p, talla="30")
        self.assertEqual(lineas(self.client), [])
        pantalon = hacer("Pantalón Negro")
        agregar(self.client, pantalon, talla="XL")
        self.assertEqual(lineas(self.client), [])

    def test_talla_se_normaliza_y_unica_la_ignora(self):
        agregar(self.client, hacer("Camisa"), talla=" xl ")
        gorra = hacer("Gorra", tipo_talla="unica")
        agregar(self.client, gorra, talla="L")
        tallas = {l.producto.nombre: l.talla for l in lineas(self.client)}
        self.assertEqual(tallas, {"Camisa": "XL", "Gorra": ""})

    def test_repetido_suma_la_cantidad_pedida(self):
        p = hacer()
        agregar(self.client, p, cantidad=2)
        agregar(self.client, p, cantidad=3)
        (l,) = lineas(self.client)
        self.assertEqual(l.cantidad, 5)

    def test_misma_prenda_en_otra_talla_o_color_es_otra_linea(self):
        p = hacer()
        v = ProductoVariante.objects.create(producto=p, color="Blanco", hex="#ffffff", stock_actual=5)
        agregar(self.client, p, "M")
        agregar(self.client, p, "L")
        agregar(self.client, p, "M", variante=v.id)
        self.assertEqual(len(lineas(self.client)), 3)

    def test_nunca_mas_que_el_stock(self):
        p = hacer(stock=3)
        agregar(self.client, p, cantidad=2)
        r = agregar(self.client, p, cantidad=2, talla="M")
        self.assertRedirects(r, f"/producto/{p.id}", fetch_redirect_response=False)
        self.assertContains(self.client.get(f"/producto/{p.id}"), "Solo quedan 3 unidades de Camisa (ya tienes 2 en tu bolsa)")
        self.assertEqual(lineas(self.client)[0].cantidad, 2)

    def test_agotado_no_se_agrega_y_el_stock_de_la_variante_es_el_suyo(self):
        p = hacer(stock=0)
        agregar(self.client, p)
        self.assertEqual(lineas(self.client), [])
        v = ProductoVariante.objects.create(producto=p, color="Rojo", hex="#ff0000", stock_actual=4)
        agregar(self.client, p, variante=v.id)
        self.assertEqual(lineas(self.client)[0].variante, v)

    def test_variante_de_otro_producto_o_producto_inactivo(self):
        p, otro = hacer("Camisa"), hacer("Buso")
        v = ProductoVariante.objects.create(producto=otro, color="Rojo", hex="#ff0000", stock_actual=4)
        agregar(self.client, p, variante=v.id)
        inactivo = hacer("Viejo", estado="inactivo")
        agregar(self.client, inactivo)
        self.assertEqual(lineas(self.client), [])

    def test_cantidad_con_basura_vale_uno(self):
        agregar(self.client, hacer(), cantidad="abc")
        self.assertEqual(lineas(self.client)[0].cantidad, 1)

    def test_el_precio_se_congela_al_agregar(self):
        p = hacer(precio=100000)
        agregar(self.client, p)
        Producto.objects.filter(pk=p.pk).update(precio=999999)
        self.assertEqual(lineas(self.client)[0].precio_unitario, 100000)

    def test_contador_del_menu(self):
        p = hacer()
        self.assertContains(self.client.get("/"), 'cart-badge">0<')
        agregar(self.client, p, cantidad=3)
        self.assertContains(self.client.get("/"), 'cart-badge">3<')


class CambiarCantidadTests(TestCase):
    def setUp(self):
        self.p = hacer(stock=5)
        agregar(self.client, self.p, cantidad=2)
        self.id = lineas(self.client)[0].id

    def cantidad(self):
        l = lineas(self.client)
        return l[0].cantidad if l else 0

    def test_botones_mas_y_menos_son_relativos(self):
        self.client.post("/carrito/actualizar", {"linea": self.id, "delta": "1", "cantidad": "2"})
        self.assertEqual(self.cantidad(), 3)
        self.client.post("/carrito/actualizar", {"linea": self.id, "delta": "-1", "cantidad": "3"})
        self.assertEqual(self.cantidad(), 2)

    def test_numero_escrito_a_mano(self):
        self.client.post("/carrito/actualizar", {"linea": self.id, "cantidad": "4"})
        self.assertEqual(self.cantidad(), 4)

    def test_menos_de_uno_quita_la_linea(self):
        self.client.post("/carrito/actualizar", {"linea": self.id, "delta": "-1", "cantidad": "2"})
        self.client.post("/carrito/actualizar", {"linea": self.id, "delta": "-1", "cantidad": "1"})
        self.assertEqual(self.cantidad(), 0)

    def test_mas_que_el_stock_se_ajusta_con_aviso(self):
        r = self.client.post("/carrito/actualizar", {"linea": self.id, "cantidad": "50"}, follow=True)
        self.assertEqual(self.cantidad(), 5)
        self.assertContains(r, "Solo quedan 5 unidades de Camisa")

    def test_basura_y_linea_inexistente_no_rompen(self):
        self.assertEqual(self.client.post("/carrito/actualizar", {"linea": self.id, "cantidad": "abc"}).status_code, 302)
        r = self.client.post("/carrito/actualizar", {"linea": "nada", "cantidad": "2"}, follow=True)
        self.assertContains(r, "ya no está en tu bolsa")

    def test_eliminar_solo_borra_esa_talla(self):
        agregar(self.client, self.p, "L")
        self.client.post("/carrito/eliminar", {"linea": self.id})
        (l,) = lineas(self.client)
        self.assertEqual(l.talla, "L")

    def test_solo_post(self):
        for url in ("/carrito/actualizar", "/carrito/eliminar", f"/carrito/agregar/{self.p.id}"):
            self.assertEqual(self.client.get(url).status_code, 405, url)


class CarritoDeUsuarioTests(TestCase):
    def test_carrito_en_base_de_datos_y_persistente(self):
        u = cliente()
        c = Client()
        c.force_login(u)
        agregar(c, hacer(), cantidad=2)
        self.assertEqual(Carrito.objects.get(user=u).items.get().cantidad, 2)
        c2 = Client()  # otro navegador
        c2.force_login(u)
        self.assertEqual(lineas(c2)[0].cantidad, 2)
        self.assertContains(c2.get("/"), 'cart-badge">2<')

    def test_no_se_puede_tocar_la_linea_de_otro_usuario(self):
        p = hacer()
        a, b = Client(), Client()
        a.force_login(cliente("a@x.co"))
        b.force_login(cliente("b@x.co"))
        agregar(a, p)
        id_de_a = lineas(a)[0].id
        b.post("/carrito/eliminar", {"linea": id_de_a})
        b.post("/carrito/actualizar", {"linea": id_de_a, "cantidad": "7"})
        self.assertEqual(lineas(a)[0].cantidad, 1)

    def test_al_iniciar_sesion_se_une_el_carrito_de_invitado(self):
        u = cliente()
        p = hacer(stock=10)
        agregar(self.client, p, "M", cantidad=2)
        agregar(self.client, p, "L", cantidad=1)
        self.client.post("/login", {"email": "ana@correo.com", "password": CLAVE})
        self.assertNotIn(SESSION_KEY, self.client.session)
        items = {(i.talla): i.cantidad for i in Carrito.objects.get(user=u).items.all()}
        self.assertEqual(items, {"M": 2, "L": 1})

    def test_la_union_suma_con_lo_que_ya_tenia_la_cuenta(self):
        u = cliente()
        p = hacer(stock=10)
        otro = Client()
        otro.force_login(u)
        agregar(otro, p, "M", cantidad=3)
        agregar(self.client, p, "M", cantidad=2)
        self.client.post("/login", {"email": "ana@correo.com", "password": CLAVE})
        self.assertEqual(Carrito.objects.get(user=u).items.get().cantidad, 5)  # 3 + 2, no se pierde la cantidad

    def test_la_union_omite_lo_que_ya_no_alcanza(self):
        u = cliente()
        p = hacer(stock=3)
        otro = Client()
        otro.force_login(u)
        agregar(otro, p, "M", cantidad=3)
        agregar(self.client, p, "M", cantidad=2)  # 3 + 2 > stock: esa línea se omite sin romper el login
        r = self.client.post("/login", {"email": "ana@correo.com", "password": CLAVE})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Carrito.objects.get(user=u).items.get().cantidad, 3)

    def test_iniciar_sesion_sin_carrito_de_invitado_no_crea_nada(self):
        u = cliente()
        self.client.post("/login", {"email": "ana@correo.com", "password": CLAVE})
        self.assertFalse(Carrito.objects.filter(user=u).exists())


class AvisosDeDisponibilidadTests(TestCase):
    def test_linea_agotada_bloquea_el_pago(self):
        p = hacer(stock=5)
        agregar(self.client, p, cantidad=2)
        Producto.objects.filter(pk=p.pk).update(stock_actual=0)
        r = self.client.get("/carrito")
        self.assertContains(r, "Agotado.")
        self.assertContains(r, "bloqueado")
        self.assertNotContains(r, 'href="/checkout"')

    def test_menos_stock_del_pedido(self):
        p = hacer(stock=5)
        agregar(self.client, p, cantidad=4)
        Producto.objects.filter(pk=p.pk).update(stock_actual=2)
        self.assertContains(self.client.get("/carrito"), "Solo quedan 2 unidades.")

    def test_producto_desactivado(self):
        p = hacer()
        agregar(self.client, p)
        Producto.objects.filter(pk=p.pk).update(estado="inactivo")
        self.assertContains(self.client.get("/carrito"), "ya no está disponible")

    def test_todo_bien_ofrece_el_pago(self):
        agregar(self.client, hacer())
        self.assertContains(self.client.get("/carrito"), 'href="/checkout"')
