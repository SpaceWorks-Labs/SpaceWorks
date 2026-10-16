"""Translate service refusals into the control panel's native permission response."""
from functools import wraps

from django.core.exceptions import PermissionDenied
from rest_framework.exceptions import APIException


def control_mutation(method):
    @wraps(method)
    def wrapped(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except APIException as exc:
            raise PermissionDenied(str(exc.detail)) from exc
    return wrapped
