"""Celery's Redis transport settings, derived from the final broker and result URLs (decision 339).

Applied in ``config/settings.py`` after the cloud task profile has had its say, so the URLs here are
the ones the worker actually uses. See ``docs/architecture/redis.md``.
"""

import ssl
from urllib.parse import parse_qs, urlsplit

# Longer than any task runs. With ``acks_late`` on the Redis transport, a message not acknowledged
# within this window is handed to another worker WHILE THE FIRST STILL RUNS IT. Celery's default
# is one hour, and a nightly backup of a large space can run longer than that. Every task is
# idempotent (docs/architecture/background-jobs.md), so this is about not doing the work twice,
# not about correctness; the cost is that a job lost with a crashed worker returns after this long
# instead of one hour, and the sweeps re-drive their own rows long before that.
VISIBILITY_TIMEOUT_SECONDS = 6 * 60 * 60

_SOCKET = {"socket_connect_timeout": 5, "socket_timeout": 30, "socket_keepalive": True}


def _tls_options(url):
    """``rediss://`` with no ``ssl_cert_reqs`` in the URL: verify the server certificate.

    Celery refuses a ``rediss://`` result backend without that parameter, and the broker's TLS
    defaults depend on the kombu version; naming it here makes both verify by default. A URL that
    states ``ssl_cert_reqs`` itself keeps exactly what it says.
    """
    parts = urlsplit(url or "")
    if parts.scheme != "rediss" or "ssl_cert_reqs" in parse_qs(parts.query):
        return None
    return {"ssl_cert_reqs": ssl.CERT_REQUIRED}


def celery_transport_settings(broker_url, result_backend, *, eager):
    if eager or not str(broker_url or "").startswith(("redis://", "rediss://")):
        return {}
    values = {
        "CELERY_BROKER_TRANSPORT_OPTIONS": {"visibility_timeout": VISIBILITY_TIMEOUT_SECONDS, **_SOCKET},
    }
    broker_tls = _tls_options(broker_url)
    if broker_tls:
        values["CELERY_BROKER_USE_SSL"] = broker_tls
    result_tls = _tls_options(result_backend)
    if result_tls:
        values["CELERY_REDIS_BACKEND_USE_SSL"] = result_tls
    return values
