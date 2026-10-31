"""Typed 409 errors for the finance ledger and the lane L5 money flows."""

from rest_framework.exceptions import APIException


class LedgerConflict(APIException):
    """A ledger, claim, confirmation or pay-link action cannot happen in this state (409)."""

    status_code = 409

    def __init__(self, detail, code, **extra):
        self.detail = {"detail": detail, "code": code, **extra}
