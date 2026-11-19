from django.db import migrations, models


def estado_a_is_active(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(estado="inactivo").update(is_active=False)


def is_active_a_estado(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(is_active=False).update(estado="inactivo")


class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_roles_iniciales")]

    operations = [
        migrations.AddField(
            model_name="user",
            name="is_active",
            field=models.BooleanField(default=True, verbose_name="activo"),
        ),
        migrations.RunPython(estado_a_is_active, is_active_a_estado),
        migrations.RemoveField(model_name="user", name="estado"),
    ]
