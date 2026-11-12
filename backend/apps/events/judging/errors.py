"""Stable programme errors; callers must establish visibility before version disclosure."""

from django.utils.translation import gettext
from rest_framework.exceptions import APIException


class ProgrammeError(APIException):
    def __init__(self, code, detail, *, status=409, current_version=None):
        self.status_code = status
        payload = {"code": code, "detail": detail, "fields": {}}
        if current_version is not None:
            payload["current_version"] = current_version
        super().__init__(payload, code=code)
        # DRF otherwise coerces integer versions into ErrorDetail strings.
        if current_version is not None:
            self.detail["current_version"] = current_version


def require_version(row, expected):
    if type(expected) is not int or expected != row.version:
        raise ProgrammeError("stale_version", gettext("This item changed."), current_version=row.version)


def invalid(detail="This action is unavailable in the current state."):
    raise ProgrammeError("invalid_transition", detail)
