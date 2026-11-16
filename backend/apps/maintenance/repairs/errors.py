"""Typed refusals of the repairs surface, in the project's `{detail, code}` error shape."""

from rest_framework import status
from rest_framework.exceptions import APIException


class RepairsError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "repairs_conflict"

    def __init__(self, detail, code=None, status_code=None):
        if status_code is not None:
            self.status_code = status_code
        code = code or self.default_code
        super().__init__({"detail": detail, "code": code}, code)


def not_eligible(detail="Only the person who used it can report a problem with it."):
    return RepairsError(detail, "reporter_not_eligible", status.HTTP_403_FORBIDDEN)


def out_of_scope(detail="This is outside the machines, items or rooms you look after."):
    return RepairsError(detail, "out_of_scope", status.HTTP_403_FORBIDDEN)


def no_consent(detail="This technician has not opted in to that channel yet."):
    return RepairsError(detail, "technician_no_consent")


def quote_not_approved(detail="Record a payout only after the quote is approved."):
    return RepairsError(detail, "quote_not_approved")


def bad_state(detail, code="issue_state_invalid"):
    return RepairsError(detail, code)
