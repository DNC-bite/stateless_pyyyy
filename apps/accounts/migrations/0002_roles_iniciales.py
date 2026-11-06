from django.db import migrations


def crear_roles(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    for nombre in ("admin", "empleado", "cliente"):
        Role.objects.get_or_create(name=nombre)


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]
    operations = [migrations.RunPython(crear_roles, migrations.RunPython.noop)]
