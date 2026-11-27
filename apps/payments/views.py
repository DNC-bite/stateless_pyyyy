import json
import logging

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from mercadopago.webhook import InvalidWebhookSignatureError, WebhookSignatureValidator
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.orders.models import Venta

from . import services
from .models import Payment, WebhookEvent
from .serializers import CreatePaymentSerializer, PaymentSerializer

logger = logging.getLogger(__name__)


class PaymentCreateView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CreatePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        venta = get_object_or_404(
            Venta,
            pk=serializer.validated_data["venta_id"],
            usuario=request.user,
            estado=Venta.Estado.PENDIENTE_PAGO,
        )

        try:
            payment, created = services.create_payment_preference(venta)
        except services.MercadoPagoError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        response_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(PaymentSerializer(payment).data, status=response_status)


class PaymentDetailView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, reference):
        payment = get_object_or_404(Payment, reference=reference, venta__usuario=request.user)
        if request.query_params.get("refresh") and payment.mp_payment_id:
            try:
                payment = services.sync_payment_from_mp(payment.mp_payment_id) or payment
            except services.MercadoPagoError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(PaymentSerializer(payment).data)


@csrf_exempt
@api_view(["POST"])
@authentication_classes([])
@permission_classes([])
def webhook(request):
    body = request.data if isinstance(request.data, dict) else {}
    topic = str(
        body.get("type")
        or body.get("action")
        or request.query_params.get("type")
        or request.query_params.get("topic")
        or ""
    )
    data_id = str(
        request.query_params.get("data.id")
        or (body.get("data") or {}).get("id")
        or request.query_params.get("id")
        or ""
    )
    request_id = request.headers.get("x-request-id", "")
    event = WebhookEvent.objects.create(
        request_id=request_id,
        topic=topic,
        data_id=data_id,
        payload=json.loads(json.dumps(body, default=str)),
    )

    secret = settings.MERCADOPAGO_WEBHOOK_SECRET.strip()
    if secret == "PEGA_EL_SECRETO_NUEVO":
        secret = ""
    if secret:
        try:
            WebhookSignatureValidator.validate(
                request.headers.get("x-signature"),
                request_id,
                data_id.lower(),
                secret,
            )
            event.signature_valid = True
        except InvalidWebhookSignatureError as exc:
            event.error = f"Firma inválida: {exc}"
            event.save(update_fields=["error"])
            logger.warning("Webhook con firma inválida (request_id=%s)", request_id)
            return Response(status=status.HTTP_401_UNAUTHORIZED)
    elif not settings.DEBUG:
        event.error = "MERCADOPAGO_WEBHOOK_SECRET no configurado"
        event.save(update_fields=["error"])
        return Response(status=status.HTTP_503_SERVICE_UNAVAILABLE)

    event.save(update_fields=["signature_valid"])
    if topic == "payment" and data_id:
        try:
            services.sync_payment_from_mp(data_id)
        except services.MercadoPagoError as exc:
            event.error = str(exc)
            event.save(update_fields=["error"])
            logger.exception("No se pudo procesar el webhook %s", data_id)
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    event.processed = True
    event.save(update_fields=["processed"])
    return Response(status=status.HTTP_200_OK)
