"""Compatibility routes stay present through replay; their duplicate writers stay frozen."""
from rest_framework.exceptions import APIException

from .notification_cutover import CutoverClosed, state


class LegacyMessagingRetired(APIException):
    status_code = 410
    default_code = "legacy_messaging_retired"
    default_detail = "Use notification channel settings, templates and personal endpoint proofs."


def deny_legacy_write():
    if not state().reconciled_at:
        raise CutoverClosed()
    raise LegacyMessagingRetired()
