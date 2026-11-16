"""Integrator-owned settings.py consumes this validated managed DB dictionary."""

from .connection import database_spec


def managed_database_configuration(url, *, environ=None):
    spec = database_spec(url, managed=True, environ=environ)
    parameters = spec.kwargs()
    result = {"ENGINE": "django.db.backends.postgresql"}
    for libpq, django in (("dbname", "NAME"), ("user", "USER"), ("password", "PASSWORD"), ("host", "HOST"), ("port", "PORT")):
        result[django] = parameters.pop(libpq, "")
    result.update(
        OPTIONS=parameters, CONN_MAX_AGE=60, CONN_HEALTH_CHECKS=True,
        DISABLE_SERVER_SIDE_CURSORS=False,
    )
    return result
