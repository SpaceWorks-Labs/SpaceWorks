"""Durable, once-only requester milestone intents for machine-service jobs.

``started``/``completed``/``cancelled`` are marked on the request's OWN row (a nullable
timestamp meaning "intent reserved", written with a queryset update so ``updated_at``
and the staff source revisions do not move) in the same transaction as the milestone,
and the owner's envelope is inserted beside it. Both are fail-closed: a reservation
failure rolls the workflow mutation back. A marker is never cleared and a suppressed
milestone is never re-reserved.

``next`` never locks or writes another member's row (C2): its once-only marker IS the
stable-key ``NotificationEnvelope`` (``get_or_create`` on
``machines.service:<request_id>:next:requester:<owner_id>``), so concurrent
re-evaluations insert at most one intent and a head that loses and reclaims first place
gets no second notice. The caller must hold the scope lock -- the ``ServiceQueue`` row
for pooled work, the bucket's ``Machine`` row for bucket work -- so the head it reads is
stable for the transaction. Reads never call into this module.
"""

from django.utils import timezone

from apps.integrations.notification_outbox import emit

from .models import MachineServiceRequest
from .notifications_p2_service_notices import MARKERS, WAITING, default_content, milestone_revision
from apps.integrations.fanout_jobs import deferred_fanout

KIND = "machines.service"


def dedup_key(request_id, event, owner_id):
    return f"{KIND}:{request_id}:{event}:requester:{owner_id}"


def valid_owner(row):
    """The existing valid-owner policy: member, else historical requester; never a stub."""
    from apps.accounts.principal_guards import is_anonymous_requester
    owner = row.member or row.requester
    if owner is None or owner.is_tenant_dump_stub or is_anonymous_requester(owner):
        return None
    return owner


def head_queryset(row):
    from .job_order import ordering
    scope = {"queue_id": row.queue_id} if row.queue_id else {"bucket_id": row.bucket_id}
    return MachineServiceRequest.objects.filter(
        makerspace_id=row.makerspace_id, status__in=WAITING, **scope,
    ).order_by(*ordering())


def _context(row, initiator):
    machine_type = row.queue.machine_type if row.queue_id else row.bucket.machine.machine_type
    return {"machine_service_request_id": row.pk, "initiator": initiator,
            "machine_id": row.assigned_machine_id, "machine_type_id": machine_type.pk}


def _emit(row, event, owner, *, marker, initiator):
    from .notifications_p2_service import scope_for
    return emit(
        makerspace=row.makerspace, recipient=owner, feature="printing", stream="printing", event=event,
        audience="requester", dedup_key=dedup_key(row.pk, event, owner.pk), source_kind=KIND,
        source_id=row.pk, revision=milestone_revision(row, event, owner.pk, marker), subject=row,
        scope=scope_for(row), context=_context(row, initiator), rendered=default_content(row, event),
        timing_policy="immediate",
    )


@deferred_fanout()
def reserve_milestone(row, event, *, initiator):
    """Mark and reserve one started/completed/cancelled intent; idempotent per row.

    The caller holds the request row lock. Returns the envelope, or None when the marker
    was already set (repeated legacy calls) or the row has no valid personal owner.
    """
    field = MARKERS[event]
    now = timezone.now()
    marked = MachineServiceRequest.objects.filter(pk=row.pk, **{f"{field}__isnull": True}).update(**{field: now})
    if not marked:
        return None
    setattr(row, field, now)
    owner = valid_owner(row)
    if owner is None:
        return None
    return _emit(row, event, owner, marker=now, initiator=initiator)


@deferred_fanout()
def reevaluate_head(row, *, initiator):
    """Reserve the once-only ``next`` intent for the accepted head of ``row``'s scope."""
    head = head_queryset(row).select_related(
        "makerspace", "member", "requester", "assigned_machine", "queue__machine_type",
        "bucket__machine__machine_type",
    ).first()
    if head is None or head.status != MachineServiceRequest.Status.ACCEPTED or head.imported_head_notified:
        return None
    owner = valid_owner(head)
    if owner is None:
        return None
    return _emit(head, "next", owner, marker=None, initiator=initiator)


def initiator_for(actor):
    """Audit/context only: a staff/member user id, or ``device`` for printer auto-apply."""
    return f"user:{actor.pk}" if getattr(actor, "pk", None) else "device"
