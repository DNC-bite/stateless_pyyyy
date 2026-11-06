#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    try:
        execute_from_command_line(sys.argv)
    except Exception as exc:  # noqa: BLE001
        from django.db.utils import OperationalError

        if not isinstance(exc, OperationalError):
            raise
        sys.stderr.write(
            "\n[STATELESS] No se pudo usar la base de datos:\n"
            f"   {exc}\n\n"
            "Qué hacer:\n"
            "  1) Para probar YA, sin instalar nada: abre el archivo .env y pon  DB_ENGINE=sqlite\n"
            "  2) Para usar MySQL: abre Docker Desktop, ejecuta  docker compose up -d  y espera ~20 segundos.\n"
            "     Revisa también DB_USER, DB_PASSWORD y DB_PORT en .env.\n"
        )
        sys.exit(1)


if __name__ == '__main__':
    main()
