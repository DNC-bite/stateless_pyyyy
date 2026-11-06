from django.core.management.base import BaseCommand
from django.db import transaction

from apps.catalog.models import Categoria, Producto, Proveedor

# Datos tomados del archivo stateless.sql, con los nombres corregidos y las imágenes locales.
# Se dejaron fuera: el producto de Cloudinary (depende de tu cuenta) y la variante con datos rotos.
PRODUCTOS = [
    ("Pantalón Negro", "essentials", 250, "Cargo_Oversize_negro_esencial.jpg", 37, "pantalon"),
    ("Pantalón OC", "essentials", 250000, "pantalon_sonido_negro_atras.png", 11, "pantalon"),
    ("Camisa Octane", "essentials", 150000, "saturado_atras_WAVES.png", 156, "auto"),
    ("Lalanta", "essentials", 56489, "onda_atras_WAVES.png", 159, "auto"),
    ("Camiseta Arakiri", "octane", 150, "Camiseta_Arakiri_frente_OCTANE.png", 159, "auto"),
    ("Dispersa", "waves", 25690, "dispersa_negra_atras_WAVES.png", 250, "auto"),
    ("Nuevo Ejemplo", "essentials", 159000, "camisa_overzice_negra_ESENCIAL.jpg", 147, "auto"),
]


class Command(BaseCommand):
    help = "Carga un proveedor y siete productos de demostración (se puede ejecutar varias veces)."

    @transaction.atomic
    def handle(self, *args, **options):
        proveedor, _ = Proveedor.objects.get_or_create(
            nombre="SA",
            defaults={
                "telefono": "3000000000",
                "correo": "contacto@proveedor-demo.com",
                "ciudad": "Bogotá",
            },
        )
        creados = 0
        for nombre, slug, precio, imagen, stock, tipo in PRODUCTOS:
            _, nuevo = Producto.objects.get_or_create(
                nombre=nombre,
                categoria=Categoria.objects.get(slug=slug),
                defaults={
                    "precio": precio,
                    "imagen": imagen,
                    "stock_actual": stock,
                    "proveedor": proveedor,
                    "tipo_talla": tipo,
                },
            )
            creados += nuevo
        self.stdout.write(self.style.SUCCESS(f"Listo: {creados} producto(s) nuevo(s) de {len(PRODUCTOS)}."))
