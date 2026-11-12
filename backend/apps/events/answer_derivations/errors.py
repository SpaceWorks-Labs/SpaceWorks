"""Safe programme errors; never interpolate a birth date or envelope."""

from django.utils.translation import gettext
from rest_framework.exceptions import APIException


class DerivationError(APIException):
    def __init__(self, code, detail, *, status=400, fields=None, **extra):
        self.status_code = status
        super().__init__({"code": code, "detail": detail, "fields": fields or {}})
        # DRF's default error conversion stringifies integers. Revision metadata
        # is a typed contract field and must remain a JSON number.
        self.detail.update(extra)


def pii_unavailable():
    return DerivationError(
        "event_pii_unavailable", gettext("Event pii unavailable."), status=503,
        readiness_action="Configure host protected-data encryption before collecting birth dates.",
    )
