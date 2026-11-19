from decimal import Decimal

from django.template import Context, Template
from django.test import SimpleTestCase, override_settings

from apps.core.utils import desglose_iva, imagen_url


class UtilsTests(SimpleTestCase):
    def test_desglose_iva_coincide_con_el_pdf(self):
        # 250.000 / 1,19 = 210.084,03 -> base 210.084 e IVA 39.916 (mitad hacia arriba)
        base, iva = desglose_iva(Decimal("250000"))
        self.assertEqual((base, iva), (Decimal("210084"), Decimal("39916")))
        self.assertEqual(base + iva, Decimal("250000"))

    def test_desglose_iva_cero(self):
        self.assertEqual(desglose_iva(None), (Decimal("0"), Decimal("0")))

    @override_settings(STATIC_URL="/static/")
    def test_imagen_url_los_tres_casos(self):
        self.assertEqual(imagen_url("https://res.cloudinary.com/x/y.webp"), "https://res.cloudinary.com/x/y.webp")
        self.assertEqual(imagen_url("/images/a.png"), "/images/a.png")
        self.assertEqual(imagen_url("a.png"), "/static/images/a.png")
        self.assertTrue(imagen_url("").endswith("placeholder.svg"))

    def test_filtro_cop(self):
        out = Template("{% load stateless %}{{ a|cop }}|{{ a|cop:'punto' }}|{{ b|cop }}").render(
            Context({"a": Decimal("25052500.00"), "b": None})
        )
        self.assertEqual(out, "25,052,500|25.052.500|0")


class RateLimitTests(SimpleTestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()

    def test_permite_hasta_el_maximo(self):
        from apps.core import ratelimit
        self.assertEqual([ratelimit.permitir("k", 2, 60) for _ in range(4)], [True, True, False, False])
        ratelimit.reiniciar("k")
        self.assertTrue(ratelimit.permitir("k", 2, 60))
