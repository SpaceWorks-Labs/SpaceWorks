"""Stable errors without provider or foreign-resource details."""
from django.utils.translation import gettext
from rest_framework.exceptions import APIException


class ProgrammeError(APIException):
    def __init__(self, code, detail, *, status=409, fields=None, version=None):
        self.status_code = status
        body = {"code": code, "detail": detail, "fields": fields or {}}
        if version is not None:
            body["current_version"] = version
        super().__init__(body)
        self.detail = body  # Preserve integer revisions in the wire contract.


def fail(code, detail, **kwargs):
    raise ProgrammeError(code, detail, **kwargs)


def check_version(row, expected):
    current = row.version if row is not None else 0
    if type(expected) is not int or expected != current:
        fail("stale_version", gettext("This item changed. Refresh and review it."), version=current)
