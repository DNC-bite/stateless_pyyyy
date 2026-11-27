from django.db import migrations

COLECCIONES = [("Essentials", "essentials"), ("Octane", "octane"), ("Waves", "waves")]


def crear_colecciones(apps, schema_editor):
    Categoria = apps.get_model("catalog", "Categoria")
    for nombre, slug in COLECCIONES:
        Categoria.objects.get_or_create(slug=slug, defaults={"nombre": nombre, "estado": True})


class Migration(migrations.Migration):
    dependencies = [("catalog", "0001_initial")]
    operations = [migrations.RunPython(crear_colecciones, migrations.RunPython.noop)]
