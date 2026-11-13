"""Security level: every credential-guessing or code-sending door has its OWN limiter, not just the generous default.

The deployment-wide default (600/min per client) stops floods, not guessing. A door that checks a secret or sends
a message must declare a dedicated throttle (`throttle_classes` or `get_throttles`), discovered from the schema:
every anonymous-capable POST under /auth/ plus every public `email-code`, `claim` and `checkout` route.
"""
import pytest
from django.urls import resolve
from rest_framework.settings import api_settings
from rest_framework.views import APIView

from tests.levels.schema_tools import operations, resolved_url

pytestmark = pytest.mark.django_db

DEFAULT = tuple(api_settings.DEFAULT_THROTTLE_CLASSES)
SENSITIVE_SUFFIXES = ("/email-code", "/claim", "/checkout", "/login", "/login-code/resend")


def _doors():
    for method, path, operation, item in operations():
        if method != "post" or {} not in operation.get("security", []):
            continue
        if path.startswith("/api/v1/auth/") or path.rstrip("/").endswith(SENSITIVE_SUFFIXES):
            yield path, operation, item


def _dedicated(view_class):
    return tuple(getattr(view_class, "throttle_classes", DEFAULT)) != DEFAULT or \
        getattr(view_class, "get_throttles", None) is not APIView.get_throttles


def test_the_door_list_is_not_empty():
    assert len(list(_doors())) >= 10


def test_every_credential_or_code_door_has_a_dedicated_throttle():
    missing = []
    for path, operation, item in _doors():
        url, problem = resolved_url("post", path, operation, item)
        if problem:
            continue
        match = resolve(url)
        cls = getattr(match.func, "cls", None) or getattr(match.func, "view_class", None)
        if cls is not None and not _dedicated(cls):
            missing.append(f"POST {path} -> {cls.__module__}.{cls.__qualname__}")
    assert not missing, "doors on the generic limiter only:\n" + "\n".join(missing)
