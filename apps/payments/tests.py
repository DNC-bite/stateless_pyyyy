import hashlib
import hmac
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.orders.models import Venta

from .models import Payment
from .services import MercadoPagoError, get_sdk, sync_payment_from_mp


@override_settings(MERCADOPAGO_ACCESS_TOKEN="TEST-token", MERCADOPAGO_WEBHOOK_SECRET="")
class PaymentApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            email="cliente@correo.com",
            password="test-password",
            name="Cliente",
        )
        self.venta = Venta.objects.create(
            usuario=self.user,
            metodo_pago=Venta.Metodo.TARJETA_CREDITO,
            total="50000.00",
        )
        self.client.force_authenticate(self.user)

    @override_settings(MERCADOPAGO_ACCESS_TOKEN="PEGA_EL_TOKEN_NUEVO")
    @patch("apps.payments.services.mercadopago.SDK")
    def test_placeholder_access_token_is_rejected_before_provider_request(self, sdk_cls):
        with self.assertRaisesMessage(MercadoPagoError, "Access Token real"):
            get_sdk()
        sdk_cls.assert_not_called()

    @override_settings(DEBUG=True, MERCADOPAGO_PUBLIC_URL="http://127.0.0.1:8081")
    @patch("apps.payments.services.mercadopago.SDK")
    def test_create_payment_uses_sale_total_from_database(self, sdk_cls):
        sdk = MagicMock()
        sdk.preference.return_value.create.return_value = {
            "status": 201,
            "response": {
                "id": "pref-123",
                "init_point": "https://mp/pay",
                "sandbox_init_point": "https://mp/sandbox-pay",
            },
        }
        sdk_cls.return_value = sdk

        response = self.client.post(
            "/api/payments/",
            {"venta_id": self.venta.pk, "unit_price": "1.00"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["total_amount"], "50000.00")
        self.assertEqual(response.data["preference_id"], "pref-123")
        self.assertEqual(response.data["init_point"], "https://mp/pay")
        sent = sdk.preference.return_value.create.call_args[0][0]
        self.assertEqual(sent["items"][0]["unit_price"], 50000.0)
        self.assertEqual(sent["external_reference"], response.data["reference"])
        self.assertNotIn("payer", sent)
        self.assertNotIn("notification_url", sent)

    @override_settings(DEBUG=True)
    @patch("apps.payments.services.mercadopago.SDK")
    def test_sandbox_recreates_preference_without_fixed_payer(self, sdk_cls):
        Payment.objects.create(
            venta=self.venta,
            title=self.venta.numero_factura,
            unit_price=self.venta.total,
            payer_email=self.user.email,
            preference_id="pref-with-fixed-payer",
            init_point="https://mp/pay",
            sandbox_init_point="https://mp/old-sandbox-pay",
        )
        sdk = MagicMock()
        sdk.preference.return_value.create.return_value = {
            "status": 201,
            "response": {
                "id": "pref-any-test-buyer",
                "init_point": "https://mp/pay",
                "sandbox_init_point": "https://mp/sandbox-pay",
            },
        }
        sdk_cls.return_value = sdk

        response = self.client.post("/api/payments/", {"venta_id": self.venta.pk}, format="json")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["preference_id"], "pref-any-test-buyer")
        self.assertEqual(response.data["payer_email"], "")
        sent = sdk.preference.return_value.create.call_args[0][0]
        self.assertNotIn("payer", sent)
        sdk.preference.return_value.create.assert_called_once()

    @override_settings(DEBUG=False, MERCADOPAGO_PUBLIC_URL="https://pagos.example.com")
    @patch("apps.payments.services.mercadopago.SDK")
    def test_production_preloads_payer_email(self, sdk_cls):
        sdk = MagicMock()
        sdk.preference.return_value.create.return_value = {
            "status": 201,
            "response": {
                "id": "pref-production",
                "init_point": "https://mp/pay",
            },
        }
        sdk_cls.return_value = sdk

        response = self.client.post("/api/payments/", {"venta_id": self.venta.pk}, format="json")

        self.assertEqual(response.status_code, 201)
        sent = sdk.preference.return_value.create.call_args[0][0]
        self.assertEqual(sent["payer"]["email"], self.user.email)
        self.assertEqual(
            sent["notification_url"],
            "https://pagos.example.com/api/payments/webhook/",
        )

    @patch("apps.payments.services.mercadopago.SDK")
    def test_repeated_create_reuses_existing_preference(self, sdk_cls):
        Payment.objects.create(
            venta=self.venta,
            title=self.venta.numero_factura,
            unit_price=self.venta.total,
            preference_id="pref-existing",
            init_point="https://mp/pay",
        )

        response = self.client.post("/api/payments/", {"venta_id": self.venta.pk}, format="json")

        self.assertEqual(response.status_code, 200)
        sdk_cls.assert_not_called()

    def test_user_cannot_create_payment_for_another_users_sale(self):
        other_user = get_user_model().objects.create_user(
            email="otro@correo.com",
            password="test-password",
            name="Otro",
        )
        other_sale = Venta.objects.create(
            usuario=other_user,
            metodo_pago=Venta.Metodo.TARJETA_CREDITO,
            total="70000.00",
        )

        response = self.client.post("/api/payments/", {"venta_id": other_sale.pk}, format="json")

        self.assertEqual(response.status_code, 404)

    @override_settings(MERCADOPAGO_WEBHOOK_SECRET="secret")
    @patch("apps.payments.services.mercadopago.SDK")
    def test_webhook_approves_payment_and_sale(self, sdk_cls):
        payment = Payment.objects.create(
            venta=self.venta,
            title=self.venta.numero_factura,
            unit_price=self.venta.total,
        )
        sdk = MagicMock()
        sdk.payment.return_value.get.return_value = {
            "status": 200,
            "response": {
                "id": 987,
                "status": "approved",
                "status_detail": "accredited",
                "external_reference": str(payment.reference),
                "payment_method_id": "visa",
                "transaction_amount": 50000,
                "currency_id": "COP",
            },
        }
        sdk_cls.return_value = sdk

        ts, request_id = "1742505638683", "req-abc"
        manifest = f"id:987;request-id:{request_id};ts:{ts};"
        digest = hmac.new(b"secret", manifest.encode(), hashlib.sha256).hexdigest()
        response = self.client.post(
            "/api/payments/webhook/?data.id=987&type=payment",
            {"type": "payment", "data": {"id": "987"}},
            format="json",
            HTTP_X_SIGNATURE=f"ts={ts},v1={digest}",
            HTTP_X_REQUEST_ID=request_id,
        )

        self.assertEqual(response.status_code, 200)
        payment.refresh_from_db()
        self.venta.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.APPROVED)
        self.assertEqual(payment.mp_payment_id, "987")
        self.assertEqual(self.venta.estado, Venta.Estado.PAGO_CONFIRMADO)
        self.assertEqual(self.venta.metodo_pago, Venta.Metodo.MERCADO_PAGO)

    @override_settings(MERCADOPAGO_WEBHOOK_SECRET="secret")
    def test_webhook_rejects_invalid_signature(self):
        response = self.client.post(
            "/api/payments/webhook/?data.id=987&type=payment",
            {"type": "payment", "data": {"id": "987"}},
            format="json",
            HTTP_X_SIGNATURE="ts=1,v1=bad",
            HTTP_X_REQUEST_ID="req-1",
        )
        self.assertEqual(response.status_code, 401)

    @patch("apps.payments.services.mercadopago.SDK")
    def test_payment_amount_mismatch_does_not_confirm_sale(self, sdk_cls):
        payment = Payment.objects.create(
            venta=self.venta,
            title=self.venta.numero_factura,
            unit_price=self.venta.total,
        )
        sdk = MagicMock()
        sdk.payment.return_value.get.return_value = {
            "status": 200,
            "response": {
                "id": 987,
                "status": "approved",
                "external_reference": str(payment.reference),
                "transaction_amount": 1,
                "currency_id": "COP",
            },
        }
        sdk_cls.return_value = sdk

        with self.assertRaises(MercadoPagoError):
            sync_payment_from_mp("987")
        self.venta.refresh_from_db()
        self.assertEqual(self.venta.estado, Venta.Estado.PENDIENTE_PAGO)
