import base64
import re
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, TestCase, override_settings

from apps.accounts.models import Role
from apps.catalog.models import Categoria, Producto, ProductoVariante, Proveedor
from apps.orders import services
from apps.orders.models import Envio, GarantiaReclamo, Venta, VentaItem

User = get_user_model()
CLAVE = "Clave-segura-9"


def cliente(email="ana@correo.com", role=None, nombre="Ana Pérez"):
    kw = {"role": role} if role else {}
    return User.objects.create_user(email, CLAVE, name=nombre, email_verified=True, **kw)


def sesion(user):
    c = Client()
    c.force_login(user)
    return c


def producto(nombre="Camisa Octane", precio=250000, stock=10):
    prov = Proveedor.objects.get_or_create(nombre="SA", defaults={"telefono": "1", "correo": "sa@prov.co", "ciudad": "B"})[0]
    return Producto.objects.create(nombre=nombre, precio=precio, stock_actual=stock, proveedor=prov,
                                   categoria=Categoria.objects.get(slug="essentials"))


def pedido(user, *, estado="pago_confirmado", envio_estado="pendiente", p=None, talla="M", cantidad=2, variante=None,
           transportadora="", guia="", metodo="tarjeta_credito"):
    p = p or producto()
    v = Venta.objects.create(usuario=user, metodo_pago=metodo, total=p.precio * cantidad, estado=estado,
                             codigo_pago="EFY-ABCD1234" if estado == "pendiente_pago" else "")
    VentaItem.objects.create(venta=v, producto=p, variante=variante, talla=talla, cantidad=cantidad, precio_unitario=p.precio)
    Envio.objects.create(venta=v, destinatario="Ana Pérez", telefono="3101234567", direccion="Carrera 11A # 93-93",
                         apartamento="Torre 2", ciudad="Bogotá", departamento="Bogotá D.C.", estado=envio_estado,
                         transportadora=transportadora, numero_guia=guia)
    return v


def texto_pdf(contenido: bytes) -> str:
    """Los PDF de reportlab guardan el texto en bloques ASCII85: se decodifican para poder comprobarlo."""
    partes = []
    for bloque in re.findall(rb"stream\r?\n(.*?)endstream", contenido, flags=re.S):
        try:
            partes.append(base64.a85decode(bloque.strip().removesuffix(b"~>"), adobe=False).decode("latin-1"))
        except Exception:  # noqa: BLE001
            partes.append(bloque.decode("latin-1", "ignore"))
    return "\n".join(partes)


class FacturaPantallaTests(TestCase):
    def setUp(self):
        self.user = cliente()
        self.c = sesion(self.user)
        self.v = pedido(self.user)
        self.url = f"/checkout/factura/{self.v.id}"

    def test_contenido(self):
        r = self.c.get(self.url)
        self.assertContains(r, f"FACTURA ST-{self.v.id:06d}")   # el mismo número que el PDF
        self.assertContains(r, "NIT: 901.458.789-1")
        self.assertContains(r, "Camisa Octane")
        self.assertContains(r, "Talla M")
        self.assertContains(r, "Carrera 11A # 93-93")
        self.assertContains(r, "Bogotá D.C.")
        self.assertContains(r, "Pago: Tarjeta de crédito")
        self.assertContains(r, "PAGO CONFIRMADO")
        # 500.000 con IVA incluido: base 420.168 e IVA 79.832 (la misma función que el PDF)
        self.assertContains(r, "$420,168")
        self.assertContains(r, "$79,832")
        self.assertContains(r, "$500,000")
        self.assertContains(r, 'href="/checkout/factura/%d/descargar"' % self.v.id)
        self.assertContains(r, f'href="/account/tracking/{self.v.id}"')

    def test_el_estado_dice_la_verdad(self):
        pendiente = pedido(self.user, estado="pendiente_pago", metodo="efecty")
        r = self.c.get(f"/checkout/factura/{pendiente.id}")
        self.assertContains(r, "PAGO PENDIENTE")
        self.assertNotContains(r, "PAGO CONFIRMADO")
        cancelada = pedido(self.user, estado="cancelado")
        self.assertContains(self.c.get(f"/checkout/factura/{cancelada.id}"), "CANCELADO")

    def test_color_y_estilos_de_impresion(self):
        p = producto("Gorra")
        var = ProductoVariante.objects.create(producto=p, color="Blanco", hex="#ffffff", stock_actual=3)
        v = pedido(self.user, p=p, variante=var, talla="")
        r = self.c.get(f"/checkout/factura/{v.id}")
        self.assertContains(r, "(Blanco)")
        self.assertContains(r, "css/invoice.css")
        from django.contrib.staticfiles import finders
        with open(finders.find("css/invoice.css"), encoding="utf-8") as f:
            self.assertIn("@media print", f.read())

    def test_permisos(self):
        self.assertEqual(sesion(cliente("otro@correo.com")).get(self.url).status_code, 404)
        self.assertEqual(self.c.get("/checkout/factura/9999").status_code, 404)
        for rol in ("admin", "empleado"):
            self.assertEqual(sesion(cliente(f"{rol}@correo.com", role=Role.objects.get(name=rol))).get(self.url).status_code, 200)
        self.assertEqual(Client().get(self.url).status_code, 302)


class FacturaPdfTests(TestCase):
    def setUp(self):
        self.user = cliente()
        self.c = sesion(self.user)
        self.v = pedido(self.user)
        self.url = f"/checkout/factura/{self.v.id}/descargar"

    def test_es_un_pdf_descargable(self):
        r = self.c.get(self.url)
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertEqual(r["Content-Disposition"], f'attachment; filename="factura-stateless-{self.v.id}.pdf"')
        self.assertTrue(r.content.startswith(b"%PDF"))
        self.assertIn("no-cache", r["Cache-Control"])

    def test_el_pdf_trae_los_mismos_datos_que_la_pantalla(self):
        t = texto_pdf(self.c.get(self.url).content)
        for esperado in (f"ST-{self.v.id:06d}", "NIT: 901.458.789-1", "Camisa Octane", "Talla M", "PAGO CONFIRMADO",
                         "$ 420,168", "$ 79,832", "$ 500,000", "GRATIS", "stateless2000@gmail.com"):
            self.assertIn(esperado, t, esperado)

    def test_estado_real_en_el_pdf(self):
        pend = pedido(self.user, estado="pendiente_pago", metodo="efecty")
        self.assertIn("PAGO PENDIENTE", texto_pdf(self.c.get(f"/checkout/factura/{pend.id}/descargar").content))
        canc = pedido(self.user, estado="cancelado")
        self.assertIn("CANCELADO", texto_pdf(self.c.get(f"/checkout/factura/{canc.id}/descargar").content))

    def test_el_subtitulo_fiscal_se_configura(self):
        with override_settings(FACTURA_SUBTITULO="Documento de Venta"):
            t = texto_pdf(self.c.get(self.url).content)
            self.assertIn("Documento de Venta", t)
            self.assertNotIn("Electr", t)
            self.assertContains(self.c.get(f"/checkout/factura/{self.v.id}"), "Documento de Venta")

    def test_permisos(self):
        self.assertEqual(sesion(cliente("otro@correo.com")).get(self.url).status_code, 404)
        self.assertEqual(Client().get(self.url).status_code, 302)
        staff = sesion(cliente("e@correo.com", role=Role.objects.get(name="empleado")))
        self.assertEqual(staff.get(self.url).status_code, 200)

    def test_un_pedido_con_muchas_lineas_no_rompe(self):
        for i in range(60):
            VentaItem.objects.create(venta=self.v, producto=producto(f"Prenda {i}"), talla="L", cantidad=1, precio_unitario=1000)
        r = self.c.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertGreater(r.content.count(b"/Type /Page\n"), 1)  # se reparte en varias páginas


class MisPedidosTests(TestCase):
    def test_solo_los_propios_del_mas_reciente_al_mas_antiguo(self):
        yo, otro = cliente(), cliente("otro@correo.com")
        a, b, ajeno = pedido(yo), pedido(yo, estado="cancelado"), pedido(otro)
        r = sesion(yo).get("/account/pedidos")
        self.assertEqual([v.id for v in r.context["ventas"]], [b.id, a.id])
        self.assertNotContains(r, f"#{ajeno.id}</h4>")
        self.assertContains(r, f'href="/account/tracking/{a.id}"')
        self.assertContains(r, "CANCELADO")
        self.assertContains(r, "#ff5555")  # los cancelados ya no salen en naranja como los pendientes

    def test_vacio_y_sesion(self):
        self.assertContains(sesion(cliente()).get("/account/pedidos"), "Aún no has realizado ninguna compra")
        self.assertEqual(Client().get("/account/pedidos").status_code, 302)

    def test_centro_de_garantias_solo_con_lo_mio(self):
        yo, otro = cliente(), cliente("otro@correo.com")
        mio = pedido(yo, p=producto("Mi Camisa"))
        pedido(otro, p=producto("Camisa Ajena"))
        GarantiaReclamo.objects.create(venta=mio, producto=mio.items.get().producto, usuario=yo, tipo_incidencia="COSTURA_ABIERTA",
                                       descripcion_cliente="Costura suelta", estado="APROBADO_GARANTIA",
                                       respuesta_admin="Te cambiamos la prenda")
        r = sesion(yo).get("/account/orders")
        self.assertContains(r, "Mi Camisa (Orden #%d)" % mio.id)   # opciones del formulario, solo de mi pedido
        self.assertNotContains(r, "Camisa Ajena")
        self.assertContains(r, "Costura Suelta o Descosida")       # el tipo con su texto, no con el código
        self.assertContains(r, "Garantía aprobada")                # el estado con su texto
        self.assertContains(r, "Te cambiamos la prenda")
        self.assertContains(r, "badge-ok")

    def test_pedido_cancelado_no_ofrece_reportar(self):
        yo = cliente()
        v = pedido(yo, estado="cancelado")
        self.assertNotContains(sesion(yo).get("/account/orders"), f'data-reportar="{v.id}"')

    def test_la_misma_prenda_en_dos_tallas_sale_una_vez(self):
        yo = cliente()
        v = pedido(yo, talla="M")
        VentaItem.objects.create(venta=v, producto=v.items.get().producto, talla="L", cantidad=1, precio_unitario=1)
        r = sesion(yo).get("/account/orders")
        self.assertEqual(len([o for o in r.context["opciones"] if o["venta"] == v.id]), 1)


class SeguimientoTests(TestCase):
    def setUp(self):
        self.user = cliente()
        self.c = sesion(self.user)

    def activos(self, v):
        return self.c.get(f"/account/tracking/{v.id}").content.decode().count("dot-active")

    def test_cada_paso_enciende_su_punto(self):
        casos = [("pendiente_pago", "pendiente", 0), ("pago_confirmado", "pendiente", 1),
                 ("en_preparacion", "preparando", 2), ("enviado", "en_curso", 3), ("entregado", "entregado", 4)]
        for estado, envio, esperados in casos:
            v = pedido(self.user, estado=estado, envio_estado=envio)
            # el CSS también menciona "dot-active" (1 vez); se cuentan solo los de la línea de tiempo
            html = self.c.get(f"/account/tracking/{v.id}").content.decode()
            self.assertEqual(len(re.findall(r'class="step-dot dot-active"', html)), esperados, estado)

    def test_efecty_sin_pagar_no_aparece_confirmado(self):
        v = pedido(self.user, estado="pendiente_pago", metodo="efecty")
        r = self.c.get(f"/account/tracking/{v.id}")
        self.assertNotContains(r, "✓")
        self.assertContains(r, "Total a Pagar")

    def test_sin_datos_inventados(self):
        v = pedido(self.user)
        r = self.c.get(f"/account/tracking/{v.id}")
        self.assertContains(r, "Por asignar")
        self.assertContains(r, "Generándose en bodega")
        self.assertNotContains(r, "Coordinadora")   # la transportadora falsa del sistema anterior
        self.assertContains(r, "Tarjeta de crédito")
        self.assertContains(r, "Carrera 11A # 93-93 · Torre 2")
        self.assertContains(r, "Bogotá, Bogotá D.C.")

    def test_con_guia_asignada(self):
        v = pedido(self.user, estado="enviado", envio_estado="en_curso", transportadora="DHL", guia="548486848654")
        r = self.c.get(f"/account/tracking/{v.id}")
        self.assertContains(r, "DHL Express")
        self.assertContains(r, "548486848654")
        self.assertContains(r, f'href="/checkout/factura/{v.id}"')

    def test_cancelado_muestra_aviso_en_vez_de_la_linea_de_tiempo(self):
        v = pedido(self.user, estado="cancelado")
        r = self.c.get(f"/account/tracking/{v.id}")
        self.assertContains(r, "PEDIDO CANCELADO")
        self.assertContains(r, "stateless2000@gmail.com")
        self.assertNotContains(r, 'class="timeline"')
        self.assertContains(r, "chip-cancelado")

    def test_permisos(self):
        v = pedido(self.user)
        self.assertEqual(sesion(cliente("otro@correo.com")).get(f"/account/tracking/{v.id}").status_code, 404)
        self.assertEqual(self.c.get("/account/tracking/9999").status_code, 404)
        self.assertEqual(sesion(cliente("e@correo.com", role=Role.objects.get(name="empleado"))).get(f"/account/tracking/{v.id}").status_code, 200)
        self.assertEqual(Client().get(f"/account/tracking/{v.id}").status_code, 302)

    def test_el_enlace_del_correo_funciona_para_su_dueno(self):
        v = pedido(self.user)
        self.assertEqual(self.c.get(f"/account/tracking/{v.id}").status_code, 200)


class GarantiaClienteTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()  # el límite por hora se guarda en la caché y no debe pasar de una prueba a otra
        self.user = cliente()
        self.c = sesion(self.user)
        self.p = producto("Camisa Octane")
        self.v = pedido(self.user, p=self.p)

    def radicar(self, **cambios):
        datos = {"ventaId": self.v.id, "productoId": self.p.id, "tipoIncidencia": "COSTURA_ABIERTA",
                 "descripcion": "La costura lateral venía suelta de fábrica."}
        datos.update(cambios)
        return self.c.post("/account/garantias/radicar", datos, follow=True)

    def test_radicar_crea_el_reclamo_con_su_proveedor(self):
        r = self.radicar()
        g = GarantiaReclamo.objects.get()
        self.assertEqual((g.usuario, g.venta, g.producto, g.proveedor, g.estado, g.tipo_incidencia),
                         (self.user, self.v, self.p, self.p.proveedor, "RADICADO", "COSTURA_ABIERTA"))
        self.assertFalse(g.notificado_proveedor)
        self.assertContains(r, f"Tu solicitud de garantía #{g.id} para la prenda &#x27;Camisa Octane&#x27; fue radicada")
        self.assertContains(r, f"#GAR-{g.id}")

    def test_no_se_puede_reclamar_sobre_el_pedido_de_otra_persona(self):
        otro = cliente("otro@correo.com")
        ajeno = pedido(otro, p=producto("Ajena"))
        r = self.radicar(ventaId=ajeno.id, productoId=ajeno.items.get().producto_id)
        self.assertContains(r, "Datos de pedido o prenda inválidos.")
        self.assertEqual(GarantiaReclamo.objects.count(), 0)

    def test_la_prenda_debe_estar_en_ese_pedido(self):
        r = self.radicar(productoId=producto("Otra prenda").id)
        self.assertContains(r, "Datos de pedido o prenda inválidos.")
        self.assertEqual(GarantiaReclamo.objects.count(), 0)

    def test_pedido_cancelado(self):
        Venta.objects.filter(pk=self.v.pk).update(estado="cancelado")
        self.assertContains(self.radicar(), "está cancelado")
        self.assertEqual(GarantiaReclamo.objects.count(), 0)

    def test_tipo_y_descripcion_validados(self):
        self.assertContains(self.radicar(tipoIncidencia="INVENTADO"), "Elige un tipo de falla")
        self.assertContains(self.radicar(descripcion="rota"), "mínimo 10 caracteres")
        self.assertContains(self.radicar(descripcion="   "), "Describe el daño")
        self.assertContains(self.radicar(ventaId="abc"), "Datos de pedido o prenda inválidos.")
        self.assertEqual(GarantiaReclamo.objects.count(), 0)

    def test_limite_por_hora(self):
        for _ in range(10):
            self.radicar()
        self.assertContains(self.radicar(), "muchos reclamos seguidos")
        self.assertEqual(GarantiaReclamo.objects.count(), 10)

    def test_post_login_y_csrf(self):
        self.assertEqual(self.c.get("/account/garantias/radicar").status_code, 405)
        self.assertEqual(Client().post("/account/garantias/radicar", {}).status_code, 302)
        estricto = Client(enforce_csrf_checks=True)
        estricto.force_login(self.user)
        self.assertEqual(estricto.post("/account/garantias/radicar", {"ventaId": self.v.id}).status_code, 403)


class CambioDeEstadoTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.user = cliente()
        self.v = pedido(self.user, estado="pendiente_pago", metodo="efecty")

    def recargar(self):
        self.v.refresh_from_db()
        return self.v, Envio.objects.get(venta=self.v)

    def test_desde_la_lista_de_ventas_sincroniza_el_envio_y_pone_fechas(self):
        r = services.cambiar_estado(self.v, estado_venta="pago_confirmado")
        v, e = self.recargar()
        self.assertEqual((v.estado, e.estado), ("pago_confirmado", "pendiente"))
        self.assertIsNotNone(e.fecha_confirmado)
        self.assertEqual((r.estado_cambio, r.notificado, len(mail.outbox)), (True, False, 0))  # "pendiente" no avisa

        r = services.cambiar_estado(self.v, estado_venta="en_preparacion")
        v, e = self.recargar()
        self.assertEqual((v.estado, e.estado), ("en_preparacion", "preparando"))
        self.assertIsNotNone(e.fecha_preparando)
        self.assertTrue(r.notificado)
        self.assertIn("EN BODEGA / PREPARACIÓN", mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].to, ["ana@correo.com"])

        services.cambiar_estado(self.v, estado_venta="enviado")
        v, e = self.recargar()
        self.assertEqual((v.estado, e.estado), ("enviado", "en_curso"))
        self.assertIsNotNone(e.fecha_en_curso)
        services.cambiar_estado(self.v, estado_venta="entregado")
        v, e = self.recargar()
        self.assertEqual((v.estado, e.estado), ("entregado", "entregado"))
        self.assertIsNotNone(e.fecha_entregado)
        self.assertEqual(e.paso_actual, 5)  # el seguimiento del cliente y la lista de ventas ya no se contradicen

    def test_desde_la_pantalla_de_envios_sincroniza_la_venta(self):
        services.cambiar_estado(self.v, estado_envio="en_curso", transportadora="DHL", numero_guia=" 548486848654 ", exigir_guia=True)
        v, e = self.recargar()
        self.assertEqual((v.estado, e.estado, e.transportadora, e.numero_guia), ("enviado", "en_curso", "DHL", "548486848654"))
        self.assertIn("EN CAMINO A TU DOMICILIO", mail.outbox[0].body)
        self.assertIn("DHL Express", mail.outbox[0].body)
        self.assertIn("548486848654", mail.outbox[0].body)
        self.assertIn(f"/account/tracking/{v.id}", mail.outbox[0].body)

    def test_en_camino_o_entregado_exigen_guia_y_no_cambian_nada_si_falta(self):
        for estado in ("en_curso", "entregado"):
            with self.assertRaises(services.EstadoInvalido):
                services.cambiar_estado(self.v, estado_envio=estado, exigir_guia=True)
        with self.assertRaises(services.EstadoInvalido):
            services.cambiar_estado(self.v, estado_envio="en_curso", transportadora="DHL", numero_guia="", exigir_guia=True)
        v, e = self.recargar()
        self.assertEqual((v.estado, e.estado, len(mail.outbox)), ("pendiente_pago", "pendiente", 0))
        # preparando no necesita guía
        services.cambiar_estado(self.v, estado_envio="preparando", exigir_guia=True)
        self.assertEqual(self.recargar()[1].estado, "preparando")

    def test_no_se_avisa_si_no_cambio_nada(self):
        services.cambiar_estado(self.v, estado_envio="preparando")
        self.assertEqual(len(mail.outbox), 1)
        r = services.cambiar_estado(self.v, estado_envio="preparando")      # guardar otra vez sin cambios
        self.assertEqual((r.estado_cambio, r.notificado, len(mail.outbox)), (False, False, 1))

    def test_corregir_solo_la_guia_si_avisa(self):
        services.cambiar_estado(self.v, estado_envio="en_curso", transportadora="DHL", numero_guia="111")
        r = services.cambiar_estado(self.v, estado_envio="en_curso", transportadora="DHL", numero_guia="222")
        self.assertEqual((r.estado_cambio, r.notificado, len(mail.outbox)), (False, True, 2))
        self.assertIn("222", mail.outbox[1].body)

    def test_volver_a_pendiente_retrocede_la_venta_solo_si_estaba_avanzada(self):
        services.cambiar_estado(self.v, estado_envio="preparando")
        services.cambiar_estado(self.v, estado_envio="pendiente")
        v, e = self.recargar()
        self.assertEqual((v.estado, e.estado), ("pago_confirmado", "pendiente"))
        nuevo = pedido(self.user, estado="pendiente_pago", metodo="efecty")
        services.cambiar_estado(nuevo, estado_envio="pendiente")
        nuevo.refresh_from_db()
        self.assertEqual(nuevo.estado, "pendiente_pago")  # un pedido sin pagar no pasa a "pagado" por tocar el envío

    def test_pedidos_cancelados_quedan_cerrados(self):
        Venta.objects.filter(pk=self.v.pk).update(estado="cancelado")
        for kwargs in ({"estado_venta": "entregado"}, {"estado_envio": "preparando"}):
            with self.assertRaises(services.EstadoInvalido):
                services.cambiar_estado(self.v, **kwargs)
        self.assertEqual(self.recargar()[0].estado, "cancelado")

    def test_no_se_cancela_por_esta_puerta_y_valores_invalidos(self):
        for kwargs in ({"estado_venta": "cancelado"}, {"estado_venta": "inventado"}, {"estado_envio": "cancelado"},
                       {"estado_envio": "inventado"}, {}, {"estado_envio": "preparando", "transportadora": "Mula"}):
            with self.assertRaises(services.EstadoInvalido, msg=str(kwargs)):
                services.cambiar_estado(self.v, **kwargs)
        self.assertEqual(self.recargar()[0].estado, "pendiente_pago")

    @override_settings(EMAIL_BACKEND="apps.accounts.test_acceso.CorreoRoto")
    def test_si_el_correo_falla_el_cambio_se_guarda(self):
        r = services.cambiar_estado(self.v, estado_venta="en_preparacion")
        self.assertEqual((r.estado_cambio, r.notificado), (True, False))
        self.assertEqual(self.recargar()[0].estado, "en_preparacion")

    def test_sin_notificar(self):
        services.cambiar_estado(self.v, estado_venta="en_preparacion", notificar=False)
        self.assertEqual(len(mail.outbox), 0)
