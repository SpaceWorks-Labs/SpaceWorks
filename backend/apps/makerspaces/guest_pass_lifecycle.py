"""Decision 223: what happens to a pass after it is issued.

* `stamp_waiver` -- the holder (or staff at the desk, with an explicit flag) records acceptance of
  the CURRENT waiver; the all-or-none triple is written together.
* `revoke_pass` -- staff, or the sponsor of their own guest. A paid day pass opens a refund case
  through `cancel_or_hold`; a pending charge is cancelled.
* `expire_due_passes` -- flips stored status once the window has ended. Reading never depends on
  it (`active_pass_for` checks the window), so a missed sweep cannot unlock anything.
* `mark_converted` -- called when the holder becomes a member (decision 223(k) join funnel).
"""
from django.db import transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.makerspaces.guest_pass_policy import GuestPassError
from apps.makerspaces.models import GuestPass, MakerspaceWaiver


def stamp_waiver(actor, guest_pass, *, at_desk=False, now=None):
    """Record acceptance of the active waiver on the pass. `at_desk` means staff witnessed it (audited)."""
    now = now or timezone.now()
    with transaction.atomic():
        row = GuestPass.objects.select_for_update().get(pk=guest_pass.pk)
        if row.status not in GuestPass.LIVE_STATUSES:
            raise GuestPassError("pass_not_live", "This pass can no longer be updated.")
        waiver = MakerspaceWaiver.objects.filter(makerspace_id=row.makerspace_id, is_active=True).first()
        if waiver is None:
            raise GuestPassError("no_waiver_published", "This space has no waiver to accept.")
        row.accepted_waiver, row.waiver_version, row.waiver_accepted_at = waiver, waiver.version, now
        row.save(update_fields=["accepted_waiver", "waiver_version", "waiver_accepted_at"])
        # Ids and the version only: the waiver body never enters the audit log.
        audit.record(actor, "membership.guest_pass_waiver_stamped", makerspace=row.makerspace, target=row,
                     meta={"waiver_version": waiver.version, "at_desk": bool(at_desk)})
    return row


def revoke_pass(actor, guest_pass, reason=""):
    from apps.payments.models import Payment, RefundCase
    from apps.payments.refund_cancellation import cancel_or_hold

    now = timezone.now()
    with transaction.atomic():
        row = GuestPass.objects.select_for_update(of=("self",)).select_related("makerspace", "product").get(pk=guest_pass.pk)
        if row.status not in GuestPass.LIVE_STATUSES:
            raise GuestPassError("pass_not_live", "This pass is already closed.")
        row.status, row.revoked_by, row.revoked_at = GuestPass.Status.REVOKED, actor, now
        row.revoked_reason = (reason or "")[:255]
        row.save(update_fields=["status", "revoked_by", "revoked_at", "revoked_reason"])
        refund_opened = False
        if row.kind == GuestPass.Kind.DAY:  # priced = a charge exists; cancel_or_hold no-ops without one
            payment = cancel_or_hold(makerspace=row.makerspace, subject_type=Payment.SubjectType.GUEST_PASS,
                                     subject_id=row.pk, actor=actor,
                                     reason_code=RefundCase.ReasonCode.STAFF_CANCELLED, cancelled_at=now)
            refund_opened = payment is not None and payment.status in (
                Payment.Status.PAID_ONLINE, Payment.Status.PAID_OFFLINE)
        # The free-text reason stays on the row (staff-only); the audit log carries ids only.
        audit.record(actor, "membership.guest_pass_revoked", makerspace=row.makerspace, target=row,
                     meta={"kind": row.kind, "refund_opened": refund_opened})
    return row


def _void_unpaid_day_charge(row, now):
    """An expired, never-settled day pass keeps no debt (spec S6). Settled money is never touched here:
    `cancel_or_hold` only voids a PENDING row, and a settled one is left alone (the pass was used)."""
    if row.kind != GuestPass.Kind.DAY:
        return False
    from apps.payments.models import Payment
    from apps.payments.refund_cancellation import cancel_pending
    payment = Payment.objects.filter(makerspace_id=row.makerspace_id, subject_id=row.pk,
                                     subject_type=Payment.SubjectType.GUEST_PASS).first()
    if payment is None or payment.status != Payment.Status.PENDING:
        return False
    cancel_pending(makerspace=row.makerspace, subject_type=Payment.SubjectType.GUEST_PASS, subject_id=row.pk,
                   actor=None)
    return True


def expire_due_passes(makerspace=None, now=None):
    """Flip live passes whose window has ended to `expired`. Returns how many changed."""
    now = now or timezone.now()
    due = GuestPass.objects.filter(status__in=GuestPass.LIVE_STATUSES, valid_until__lte=now)
    if makerspace is not None:
        due = due.filter(makerspace=makerspace)
    count = 0
    for row_id in list(due.values_list("pk", flat=True)[:500]):
        with transaction.atomic():
            row = GuestPass.objects.select_for_update().select_related("makerspace").get(pk=row_id)
            if row.status not in GuestPass.LIVE_STATUSES or row.valid_until > now:
                continue
            row.status = GuestPass.Status.EXPIRED
            row.save(update_fields=["status"])
            voided = _void_unpaid_day_charge(row, now)
            audit.record(None, "membership.guest_pass_expired", makerspace=row.makerspace, target=row,
                         meta={"charge_voided": voided})
            count += 1
    return count


def mark_converted(membership, actor=None):
    """The holder became a member: close their unconverted passes at this space as `converted`."""
    rows = GuestPass.objects.select_for_update().filter(
        makerspace_id=membership.makerspace_id, holder_id=membership.user_id,
    ).exclude(status__in=(GuestPass.Status.REVOKED, GuestPass.Status.CONVERTED, GuestPass.Status.EXPIRED))  # m21: history stays
    count = 0
    with transaction.atomic():
        for row in rows:
            row.status, row.converted_membership = GuestPass.Status.CONVERTED, membership
            row.save(update_fields=["status", "converted_membership"])
            audit.record(actor, "membership.guest_pass_converted", makerspace=membership.makerspace, target=row,
                         meta={"membership_id": membership.pk})
            count += 1
    return count
