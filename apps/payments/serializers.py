from rest_framework import serializers

from .models import Payment


class CreatePaymentSerializer(serializers.Serializer):
    venta_id = serializers.IntegerField(min_value=1)


class PaymentSerializer(serializers.ModelSerializer):
    venta_id = serializers.IntegerField(read_only=True)
    total_amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = Payment
        fields = [
            "reference",
            "venta_id",
            "title",
            "description",
            "quantity",
            "unit_price",
            "total_amount",
            "currency_id",
            "payer_email",
            "status",
            "status_detail",
            "preference_id",
            "init_point",
            "sandbox_init_point",
            "mp_payment_id",
            "payment_method",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
