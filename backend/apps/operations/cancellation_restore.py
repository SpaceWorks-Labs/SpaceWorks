"""Exact undo contract; adapters own resource locks, eligibility and admission math."""

from datetime import timedelta

from rest_framework.exceptions import APIException

RESTORE_WINDOW = timedelta(minutes=5)


class RestoreRefused(APIException):
    status_code = 409
    default_code = "restore_refused"

    def __init__(self, reason, detail):
        super().__init__({"code": reason, "detail": detail})


def record_cancellation(instance, *, now):
    instance.status_before_cancel = instance.status
    instance.cancelled_at = now
    return ("cancelled_at", "status_before_cancel")


def restore_deadline(instance):
    return instance.cancelled_at + RESTORE_WINDOW if instance.cancelled_at else None


def require_restorable(instance, *, now, cancelled_status, allowed_statuses,
                       has_charge=False, has_consumption=False, would_charge=False):
    if instance.status != cancelled_status:
        raise RestoreRefused("not_cancelled", "Only a cancelled record can be restored.")
    if instance.status_before_cancel not in allowed_statuses or instance.cancelled_at is None:
        raise RestoreRefused("missing_provenance", "This cancellation has no restorable prior state.")
    if not instance.cancelled_at <= now < restore_deadline(instance):
        raise RestoreRefused("window_expired", "The five-minute undo window has expired.")
    if has_charge:
        raise RestoreRefused("historical_charge", "A record with a historical charge cannot be restored.")
    if has_consumption:
        raise RestoreRefused("consumed_code", "Invite or promo consumption cannot be restored.")
    if would_charge:
        raise RestoreRefused("charge_required", "Ordinary admission would require a charge.")
    return instance.status_before_cancel


def require_exact_restore(previous, admitted):
    if previous != admitted:
        raise RestoreRefused("admission_changed", "Current admission cannot restore the original status.")
