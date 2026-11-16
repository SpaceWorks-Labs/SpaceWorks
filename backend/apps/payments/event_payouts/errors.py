"""Typed safe errors shared by domain adapters and permanent finance services."""
from rest_framework.exceptions import APIException


class PayoutError(APIException):
    status_code = 409

    def __init__(self, code, *, status=409, **fields):
        self.status_code = status
        super().__init__({"code": code, "detail": code.replace("_", " ").capitalize() + ".", "fields": fields})


def require(condition, code, *, status=409, **fields):
    if not condition:
        raise PayoutError(code, status=status, **fields)
