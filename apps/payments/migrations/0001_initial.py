import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("orders", "0002_mercado_pago_method"),
    ]

    operations = [
        migrations.CreateModel(
            name="Payment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reference", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("title", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True)),
                ("quantity", models.PositiveIntegerField(default=1)),
                ("unit_price", models.DecimalField(decimal_places=2, max_digits=12)),
                ("currency_id", models.CharField(default="COP", max_length=3)),
                ("payer_email", models.EmailField(blank=True, max_length=254)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pendiente"),
                            ("approved", "Aprobado"),
                            ("authorized", "Autorizado"),
                            ("in_process", "En proceso"),
                            ("in_mediation", "En mediación"),
                            ("rejected", "Rechazado"),
                            ("cancelled", "Cancelado"),
                            ("refunded", "Reembolsado"),
                            ("charged_back", "Contracargo"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("status_detail", models.CharField(blank=True, max_length=100)),
                ("preference_id", models.CharField(blank=True, db_index=True, max_length=100)),
                ("init_point", models.URLField(blank=True, max_length=500)),
                ("sandbox_init_point", models.URLField(blank=True, max_length=500)),
                ("mp_payment_id", models.CharField(blank=True, db_index=True, max_length=50)),
                ("payment_method", models.CharField(blank=True, max_length=50)),
                ("raw_response", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "venta",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="pagos",
                        to="orders.venta",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="WebhookEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("request_id", models.CharField(blank=True, db_index=True, max_length=100)),
                ("topic", models.CharField(blank=True, max_length=50)),
                ("data_id", models.CharField(blank=True, db_index=True, max_length=50)),
                ("payload", models.JSONField(default=dict)),
                ("signature_valid", models.BooleanField(default=False)),
                ("processed", models.BooleanField(default=False)),
                ("error", models.TextField(blank=True)),
                ("received_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["-received_at"]},
        ),
    ]
