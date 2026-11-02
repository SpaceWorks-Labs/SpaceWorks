"""Exits from pending/accepted (inventory D1, #77): withdraw/cancel and pickup expiry.

Both are terminal transitions owned by the workflow module (re-exported through
``workflow.py``). An accepted request's reservation goes back to available through the
availability module in the same transaction, and a claimed waitlist hold is released.
Nothing was charged before issue, so no loan charge seam is involved.
"""

import logging

from django.db import transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.hardware_requests.models import HardwareRequest
from apps.hardware_requests.workflow_errors import InvalidTransition
from apps.hardware_requests.workflow_utils import locked_request
from apps.inventory import availability
from apps.makerspaces.platform import feature_enabled

logger = logging.getLogger(__name__)
CANCELLABLE = (HardwareRequest.Status.PENDING_APPROVAL, HardwareRequest.Status.ACCEPTED)
WITHDRAWALS = "loans.withdrawals"


def _close(locked, status, actor):
    released = {}
    if locked.status == HardwareRequest.Status.ACCEPTED:
        released = availability.release_request_reservation(locked)
    from apps.hardware_requests.waitlist import release_claim
    release_claim(locked)
    locked.status = status
    locked.closed_by = actor
    locked.closed_at = timezone.now()
    locked.save(update_fields=["status", "closed_by", "closed_at", "updated_at"])
    return sum(released.values())


def owner_may_cancel(actor, request):
    """The signed-in requester may withdraw their own request while `loans.withdrawals` is on."""
    return bool(actor and getattr(actor, "is_authenticated", False) and request.requester_id == actor.pk
                and not request.anonymous_idempotency_key_fingerprint
                and request.status in CANCELLABLE
                and feature_enabled(request.makerspace, WITHDRAWALS))


def cancel_request(actor, request, *, by_owner, reason=""):
    """Withdraw a pending or accepted request. Authority is checked by the caller:
    the requester themself (``by_owner``) or staff holding the review action."""
    reason = str(reason or "").strip()[:500]
    with transaction.atomic():
        locked = locked_request(request)
        if by_owner and not owner_may_cancel(actor, locked):
            raise InvalidTransition("Only the requester can withdraw this request.")
        if locked.status not in CANCELLABLE:
            raise InvalidTransition(f"Cannot cancel hardware request with status {locked.status}.")
        was = locked.status
        released = _close(locked, HardwareRequest.Status.CANCELLED, actor)
        audit.record(actor, "request.cancelled", makerspace=locked.makerspace, target=locked,
                     meta={"from_status": was, "by_owner": bool(by_owner), "reason": reason,
                           "released_units": released})
        from apps.hardware_requests.notifications_loans import notify_closed
        notify_closed(locked, "cancelled")
        return locked


def expire_request(request, *, now=None):
    """Expire one accepted request whose pickup deadline has passed (system actor)."""
    now = now or timezone.now()
    with transaction.atomic():
        locked = locked_request(request)
        if (locked.status != HardwareRequest.Status.ACCEPTED or not locked.pickup_until
                or locked.pickup_until > now or not feature_enabled(locked.makerspace, "loans.pickup_windows")):
            return None
        from apps.tenant_migration.gate_runtime import assert_write_allowed
        assert_write_allowed(locked.makerspace_id)
        released = _close(locked, HardwareRequest.Status.EXPIRED, None)
        audit.record(None, "request.expired", makerspace=locked.makerspace, target=locked,
                     meta={"pickup_until": locked.pickup_until.isoformat(), "released_units": released})
        from apps.hardware_requests.notifications_loans import notify_closed
        notify_closed(locked, "expired")
        return locked


def expire_due_requests(*, now=None, limit=200):
    """Scheduled sweep: expire accepted requests past their pickup deadline; lapse offers.

    Bounded, and each row runs inside its own tenant boundary (skip-and-count when the
    source gate is closed), the same contract as the return reminders.
    """
    from apps.accounts import rbac
    from apps.operations.cloud_jobs import bounded
    from apps.tenant_migration.gate_runtime import fanout_tenant_write
    now = now or timezone.now()
    rows = rbac.scope_for_scheduled_work(HardwareRequest.objects.filter(
        status=HardwareRequest.Status.ACCEPTED, pickup_until__lte=now,
        makerspace__enabled_features__contains=["loans.pickup_windows"],
    )).order_by("pickup_until", "id")[:max(int(limit), 1)]
    counts = {"expired": 0, "skipped": 0}
    for row in bounded.page(rows, "loan-pickups"):
        with fanout_tenant_write(row.makerspace_id, operation="loan_pickup_expiry", counts=counts) as go:
            if not go:
                continue
            try:
                counts["expired"] += int(expire_request(row, now=now) is not None)
            except Exception:
                counts["skipped"] += 1
                logger.exception("Pickup expiry failed for request %s", row.pk)
    from apps.hardware_requests.waitlist import lapse_due_offers
    counts["lapsed"] = lapse_due_offers(now=now)
    return counts
