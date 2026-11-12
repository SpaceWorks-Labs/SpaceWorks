"""Delivery-time checks and content for the four requester milestone notices.

next / started / completed / cancelled are OWNER SELF-NOTICES: the recipient owns the
subject, so their sender authority is the owner's current ownership plus live account
standing plus the immutable marker (or, for ``next``, the stable envelope key and the
request still being the accepted head). The initiating staff user, member or device is
audit/context only and is never re-checked -- losing staff scope must not suppress a
requester's own notice, and a device-applied completion (no actor) still delivers.
This is a deliberate, documented exception in docs/notification-contract.md.

Wired from ``notifications_p2_service`` under the one ``machines.service`` source kind.
"""

import json
import logging

from apps.accounts import rbac
from apps.hardware_requests.notifications_p2 import content, revision
from apps.integrations.email_templates import printing_context, render
from apps.integrations.notification_links import local_link
from apps.makerspaces.platform import module_enabled

from .models import MachineServiceRequest

logger = logging.getLogger(__name__)
MILESTONES = frozenset({"next", "started", "completed", "cancelled"})
MARKERS = {"started": "started_notice_at", "completed": "completed_notice_at", "cancelled": "cancelled_notice_at"}
WAITING = (MachineServiceRequest.Status.PENDING, MachineServiceRequest.Status.ACCEPTED)
_COPY = {
    "next": ("Your {label} request #{id} is next",
             "Your {label} request #{id} is next among approved jobs. Staff start it when a compatible "
             "machine is free; check its estimated start in your account."),
    "started": ("Your {label} request #{id} has started",
                "Your {label} request #{id} has started. We'll let you know when it is ready to collect."),
    "completed": ("Your {label} request #{id} is ready to collect",
                  "Your job finished and is ready to collect ({label} request #{id})."),
    "cancelled": ("Your {label} request #{id} was cancelled",
                  "Your {label} request #{id} was cancelled. Nothing was charged for it."),
}


def is_milestone(envelope):
    return envelope.audience == "requester" and envelope.event in MILESTONES


def milestone_revision(row, event, owner_id, marker=None):
    stamp = marker.isoformat() if marker is not None else "head"
    return revision(event, stamp, owner_id, row.queue_id, row.bucket_id)


def _machine_type(row):
    return row.queue.machine_type if row.queue_id else row.bucket.machine.machine_type


def default_content(row, event):
    """Safe built-in copy: no title, contact data or tracking token."""
    from .printer_capabilities import is_printer_type
    label = "print" if is_printer_type(_machine_type(row)) else "machine service"
    subject, text = _COPY[event]
    values = {"label": label, "id": row.pk}
    return {"subject": subject.format(**values), "text": text.format(**values), "html": "",
            "link": local_link(row.makerspace, "member")}


def milestone_content(row, event):
    """Tenant-authored printer templates render here, at delivery, never in the domain
    transaction; any failure falls back to the default copy (C9)."""
    from .printer_capabilities import is_printer_type
    from .service_printing_emails import _projection
    fallback = default_content(row, event)
    if not is_printer_type(_machine_type(row)):
        return fallback
    try:
        context = {**printing_context(_projection(row), "", ""), "status_url": fallback["link"]}
        rendered = render(row.makerspace, "printing", "requester", event, context, machine_type=_machine_type(row))
        return content(rendered, link=fallback["link"])
    except Exception:
        logger.warning("machine_service_milestone_render_failed", extra={"request_id": row.pk, "event": event})
        return fallback


def _load(envelope):
    return rbac.scope_notification_policy(MachineServiceRequest.objects.all(),
        makerspace_id=envelope.makerspace_id).select_related(
        "makerspace", "requester", "member", "queue__machine_type", "bucket__machine__machine_type",
    ).filter(pk=envelope.source_id).first()


def is_accepted_head(row):
    """Accepted position 1 within its own bucket/queue; running and pending rows excluded."""
    if row.status != MachineServiceRequest.Status.ACCEPTED:
        return False
    from .service_queue_notices import head_queryset
    return head_queryset(row).values_list("pk", flat=True).first() == row.pk


def eligible(envelope):
    row = _load(envelope)
    if row is None or envelope.event not in MILESTONES:
        return False
    owner = row.member or row.requester
    if owner is None or owner.pk != envelope.recipient_id or getattr(owner, "is_tenant_dump_stub", False):
        return False
    if not (owner.is_active and owner.access_status == "active"):
        return False
    space = row.makerspace
    if not module_enabled(space, "machine_service") or not module_enabled(space, "machines"):
        return False
    if envelope.event == "next":
        if envelope.revision != milestone_revision(row, "next", owner.pk) or not is_accepted_head(row):
            return False
    else:
        marker = getattr(row, MARKERS[envelope.event])
        if marker is None or envelope.revision != milestone_revision(row, envelope.event, owner.pk, marker):
            return False
    from apps.hardware_requests.notifications_p2_email import source_ready
    return source_ready(envelope)


def render_envelope(envelope):
    if not is_milestone(envelope):
        return json.loads(envelope.message_body or "{}")
    row = _load(envelope)
    if row is None:
        return json.loads(envelope.message_body or "{}")
    return milestone_content(row, envelope.event)
