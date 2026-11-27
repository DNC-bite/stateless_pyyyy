"""Límite simple de intentos por ventana de tiempo (usa la caché de Django)."""
from django.core.cache import cache


def ip_del_cliente(request) -> str:
    return request.META.get("REMOTE_ADDR", "") or "?"


def permitir(clave: str, maximo: int, ventana: int) -> bool:
    """Cuenta un intento. Devuelve False cuando ya se superó el máximo de la ventana."""
    clave = f"rl:{clave}"
    cache.add(clave, 0, ventana)
    try:
        n = cache.incr(clave)
    except ValueError:  # expiró justo ahora
        cache.set(clave, 1, ventana)
        n = 1
    return n <= maximo


def superado(clave: str, maximo: int) -> bool:
    """Consulta sin contar un intento nuevo."""
    return (cache.get(f"rl:{clave}") or 0) >= maximo


def reiniciar(clave: str) -> None:
    cache.delete(f"rl:{clave}")
