import logging

import requests
from django.conf import settings

log = logging.getLogger(__name__)


class IAError(Exception):
    """Error al solicitar una respuesta al modelo local."""


def responder_ollama(mensajes, *, formato=None):
    """Envía mensajes a la instancia local de Ollama y devuelve el contenido."""
    cuerpo = {
        "model": settings.OLLAMA_MODEL,
        "messages": mensajes,
        "stream": False,
        "options": {"num_ctx": settings.OLLAMA_NUM_CTX},
    }
    if formato:
        cuerpo["format"] = formato

    try:
        respuesta = requests.post(
            f"{settings.OLLAMA_URL}/api/chat",
            json=cuerpo,
            timeout=settings.OLLAMA_TIMEOUT,
        )
        respuesta.raise_for_status()
        contenido = respuesta.json()["message"]["content"]
    except requests.Timeout as exc:
        log.warning("El modelo local superó el tiempo máximo de respuesta (%s s)", settings.OLLAMA_TIMEOUT)
        raise IAError(
            f"La IA local tardó más de {settings.OLLAMA_TIMEOUT} segundos. "
            "Prueba un modelo más pequeño o reduce OLLAMA_NUM_CTX; un contexto grande requiere más memoria."
        ) from exc
    except requests.ConnectionError as exc:
        log.warning("No fue posible conectar con Ollama en la dirección configurada.")
        raise IAError(
            "No se pudo conectar con Ollama. Verifica que el servicio esté activo y que OLLAMA_URL sea correcto."
        ) from exc
    except requests.HTTPError as exc:
        estado = exc.response.status_code if exc.response is not None else "desconocido"
        log.warning("Ollama rechazó la solicitud con HTTP %s", estado)
        raise IAError(
            f"Ollama respondió con un error HTTP {estado}. Verifica el modelo y su configuración."
        ) from exc
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        log.warning("No fue posible obtener respuesta del modelo local de IA: %s", exc)
        raise IAError(
            "Ollama no pudo completar la solicitud. Verifica el servicio, el modelo y su configuración."
        ) from exc

    if not isinstance(contenido, str) or not contenido.strip():
        raise IAError("El modelo de IA devolvió una respuesta vacía. Inténtalo de nuevo.")
    return contenido.strip()
