from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

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
