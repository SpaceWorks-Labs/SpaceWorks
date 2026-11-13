"""Every error body carries a machine-readable `code` (decision 481(2)).

DRF's own errors (NotAuthenticated, PermissionDenied, NotFound, MethodNotAllowed,
Throttled, ParseError, a ValidationError raised with a top-level `detail`, and Django's
Http404/PermissionDenied that DRF converts) render as `{"detail": ...}` alone, while the
shared `HardwareRequestError` component marks `code` required, so a client generated
from the schema could not decode them. The code added is DRF's own (`exc.get_codes()` /
`default_code`); `detail` and field-keyed bodies are left exactly as DRF wrote them.
"""
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import exceptions


def _drf_code(exc):
    if isinstance(exc, Http404):
        return exceptions.NotFound.default_code
    if isinstance(exc, DjangoPermissionDenied):
        return exceptions.PermissionDenied.default_code
    codes = exc.get_codes() if isinstance(exc, exceptions.APIException) else None
    if isinstance(codes, dict):
        codes = codes.get("detail")
    if isinstance(codes, list):
        codes = codes[0] if len(codes) == 1 else None
    if isinstance(codes, str):
        return codes
    return getattr(exc, "default_code", None) or exceptions.APIException.default_code


def add_error_code(exc, response):
    """Add DRF's code to a `{"detail": ...}` body that has none; any other body is untouched.

    `response.framework_code` marks the addition, so a surface with its own error vocabulary
    (the event programme views' `{code, detail, fields}`) still recognises a framework error.
    """
    data = getattr(response, "data", None)
    if isinstance(data, dict) and "detail" in data and "code" not in data:
        data["code"] = _drf_code(exc)
        response.framework_code = True
    return response
