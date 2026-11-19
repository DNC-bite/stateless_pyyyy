from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="venta",
            name="metodo_pago",
            field=models.CharField(
                choices=[
                    ("tarjeta_credito", "Tarjeta de crédito"),
                    ("paypal", "PayPal"),
                    ("shop_pay", "Shop Pay"),
                    ("google_pay", "Google Pay"),
                    ("efecty", "Efecty"),
                    ("nequi", "Nequi"),
                    ("pse", "PSE"),
                    ("mercado_pago", "Mercado Pago"),
                    ("tarjeta", "Tarjeta"),
                ],
                max_length=20,
            ),
        ),
    ]
