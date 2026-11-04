"""Review edges of the job lifecycle (#141, #142 OQ-2/3/4/5/14): needs changes and quotes.

Part of the sole transition authority (`service_workflow`): same write fence, same lock
order (request -> scope), one audit row and one notice per edge.

* staff ask for changes (pending / quote sent / in queue -> needs changes); the member
  resubmits (-> submitted) with a note and new files;
* staff send a quote priced by L15 `pricing.quote()` (-> quote sent, valid 7 days); the
  member approves with the digest they saw (409 `price_changed` otherwise), or declines;
  a prepaid type raises the quoted charge and the job queues once it is settled;
* a job waiting on the member keeps its place if they answer within 3 days (OQ-5).
"""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.machines import job_policy
from apps.machines.job_order import answered_anchor
from apps.machines.models import MachineServiceRequest
from apps.machines.service_errors import ServiceConsumptionInvalid, ServiceInvalidTransition
from apps.machines.service_queue_notices import initiator_for, reevaluate_head
from apps.machines.service_workflow_helpers import (
    _assert_request_write_allowed, _audit_transition, _lock_scope, _locked_request, _require_edge,
    _require_module,
)

Status = MachineServiceRequest.Status
CHANGE_CODES = ("file_problem", "wrong_format", "too_large", "split_needed", "material_mismatch",
                "missing_details", "other")


def _notify(row, event):
    from apps.machines.notifications_job_flow import notify_job
    notify_job(row, event)


def _clear_quote(row):
    row.quote_snapshot, row.quote_digest, row.quote_expires_at = None, "", None
    row.quote_reminded_at = row.quote_approved_at = None


def _open(row):
    _assert_request_write_allowed(row)
    locked = _locked_request(row)
    locked.refresh_from_db()
    _require_module(locked.makerspace)
    return locked


def _require_owner(locked, member):
    if locked.member_id is None or locked.member_id != getattr(member, "pk", None):
        raise ServiceInvalidTransition("Only the person who asked for this job can do that.")


def request_changes(service_request, actor, *, code, message):
    if code not in CHANGE_CODES or not str(message or "").strip():
        raise ServiceConsumptionInvalid("Choose a reason and write what the member should change.")
    with transaction.atomic():
        locked = _open(service_request)
        _require_edge(locked, Status.CHANGES_REQUESTED)
        if locked.status == Status.QUOTED and locked.quote_approved_at:
            raise ServiceInvalidTransition("The member already approved this quote.")
        _lock_scope(locked)
        was = locked.status
        _clear_quote(locked)
        locked.status, locked.handled_by = Status.CHANGES_REQUESTED, actor
        locked.changes_requested_at, locked.changes_code = timezone.now(), code
        locked.changes_message = str(message).strip()[:4000]
        locked.save()
        _audit_transition(actor, locked, "changes_requested", extra={"previous_status": was, "code": code})
        if was == Status.ACCEPTED:
            reevaluate_head(locked, initiator=initiator_for(actor))
        _notify(locked, "changes_requested")
        return locked


def resubmit(service_request, member, *, note="", file_ids=()):
    with transaction.atomic():
        locked = _open(service_request)
        _require_owner(locked, member)
        _require_edge(locked, Status.PENDING)
        if locked.status != Status.CHANGES_REQUESTED:
            raise ServiceInvalidTransition("Only a job that needs changes can be resubmitted.")
        _lock_scope(locked)
        locked.queued_at = answered_anchor(locked, locked.changes_requested_at)
        locked.status, locked.member_note = Status.PENDING, str(note or "").strip()[:4000]
        locked.save()
        for file_id in file_ids:
            from apps.machines.job_files import attach_job_file
            attach_job_file(locked, file_id=file_id, actor=member)
        _audit_transition(member, locked, "resubmitted", extra={"file_count": len(file_ids)})
        _notify(locked, "resubmitted")
        return locked


def quote_preview(row, *, minutes, quantity=None, pool=None, machine=None):
    from apps.payments.pricing import quote
    machine_type = row.queue.machine_type if row.queue_id else row.bucket.machine.machine_type
    return quote(row.makerspace, "machines", None, row.member or row.requester, params={
        "machine": machine, "machine_type": machine_type, "pool": pool, "minutes": minutes,
        "quantity": quantity or 0})


def send_quote(service_request, actor, *, estimated_minutes, quantity=None, pool=None, machine=None, note=""):
    with transaction.atomic():
        locked = _open(service_request)
        _require_edge(locked, Status.QUOTED)
        if locked.status == Status.QUOTED and locked.quote_approved_at:
            raise ServiceInvalidTransition("The member already approved this quote.")
        _lock_scope(locked)
        priced = quote_preview(locked, minutes=estimated_minutes, quantity=quantity, pool=pool, machine=machine)
        if priced.total <= 0:
            raise ServiceInvalidTransition("This job is free; accept it instead of quoting.")
        was, now = locked.status, timezone.now()
        locked.status, locked.handled_by, locked.estimated_minutes = Status.QUOTED, actor, int(estimated_minutes)
        locked.quote_snapshot, locked.quote_digest = priced.to_snapshot(), priced.digest
        locked.quoted_at, locked.quote_expires_at = now, now + timedelta(days=job_policy.QUOTE_VALID_DAYS)
        locked.quote_reminded_at = locked.quote_approved_at = None
        locked.prepay = job_policy.prepay(locked.makerspace, priced_type(locked))
        if note:
            locked.reason = str(note).strip()
        locked.save()
        _audit_transition(actor, locked, "requoted" if was == Status.QUOTED else "quoted", extra={
            "total": str(priced.total), "currency": priced.currency, "digest": priced.digest,
            "prepay": locked.prepay})
        _notify(locked, "quoted")
        return locked


def priced_type(row):
    return row.queue.machine_type if row.queue_id else row.bucket.machine.machine_type


def member_quote(snapshot):
    """The member-facing slice of a frozen quote: total, currency, line labels and nets, digest."""
    return {"total": snapshot.get("total"), "currency": snapshot.get("currency"),
            "lines": [{"label": line.get("label"), "net": line.get("net")} for line in snapshot.get("lines", [])],
            "digest": snapshot.get("digest")}


def approve_quote(service_request, member, *, digest):
    from apps.machines import job_charges
    with transaction.atomic():
        locked = _open(service_request)
        _require_owner(locked, member)
        if locked.status != Status.QUOTED or locked.quote_approved_at:
            raise ServiceInvalidTransition("There is no quote waiting for your approval.")
        if locked.quote_expires_at and locked.quote_expires_at <= timezone.now():
            raise ServiceInvalidTransition("This quote has expired.")
        if digest != locked.quote_digest:
            from apps.payments.pricing.errors import PriceChanged
            raise PriceChanged(quote=member_quote(locked.quote_snapshot or {}))
        _lock_scope(locked)
        locked.quote_approved_at = timezone.now()
        if locked.prepay:
            locked.save()
            job_charges.raise_prepay(locked, locked.handled_by)
            _audit_transition(member, locked, "quote_approved", extra={"prepay": True})
            _notify(locked, "quote_approved")
            return locked
        _enter_queue(locked, locked.quoted_at, member)
        _audit_transition(member, locked, "quote_approved", extra={"prepay": False})
        _notify(locked, "quote_approved")
        return locked


def _enter_queue(locked, waited_since, actor, *, now=None):
    locked.queued_at = answered_anchor(locked, waited_since, now=now)
    locked.status, locked.accepted_at = Status.ACCEPTED, timezone.now()
    locked.accepted_by = locked.accepted_by or locked.handled_by
    locked.save()
    reevaluate_head(locked, initiator=initiator_for(actor))


def promote_prepaid(service_request, *, actor=None):
    """A prepaid quote whose charge is settled joins the queue (sweep or staff "queue now")."""
    from apps.machines import job_charges
    with transaction.atomic():
        locked = _open(service_request)
        payment = job_charges.payment_for(locked)
        if locked.status != Status.QUOTED or not locked.prepay or not job_charges.settled(payment):
            return None
        _lock_scope(locked)
        _enter_queue(locked, locked.quoted_at, actor, now=timezone.now())
        _audit_transition(actor, locked, "prepaid_queued", extra={"payment_id": payment.pk})
        _notify(locked, "quote_approved")
        return locked


def decline_quote(service_request, member, *, expired=False):
    with transaction.atomic():
        locked = _open(service_request)
        if not expired:
            _require_owner(locked, member)
        if locked.status != Status.QUOTED or locked.quote_approved_at:
            raise ServiceInvalidTransition("There is no open quote to decline.")
        if expired and (locked.quote_expires_at is None or locked.quote_expires_at > timezone.now()):
            return None
        _lock_scope(locked)
        locked.status, locked.cancelled_at = Status.CANCELLED, timezone.now()
        locked.save()
        event = "quote_expired" if expired else "quote_declined"
        _audit_transition(None if expired else member, locked, event)
        _notify(locked, event)
        return locked
