"""Machine-service parity on the existing printing notification category."""
from django.utils.translation import gettext
from apps.integrations.notification_links import local_link
from apps.accounts import rbac
from apps.hardware_requests.notifications_p2 import content, fanout, revision
from apps.integrations.destinations import NotificationScope
from apps.integrations.email_templates import printing_context, render
from apps.integrations.notification_sources import NotificationSource, register_source
from apps.hardware_requests.notifications_p2 import safe_adapter
from apps.makerspaces.platform import module_enabled
from .models import MachineServiceRequest

KIND = "machines.service"
EVENTS = {"submitted", "accepted", "rejected", "started", "completed", "failed", "collected", "reprinted", "cancelled"}
# Requester legs of these events are durable owner self-notices (service_queue_notices).
OWNER_MILESTONES = {"started", "completed", "cancelled"}


def machine_type(row):
    return row.queue.machine_type if row.queue_id else row.bucket.machine.machine_type


def scope_for(row):
    return NotificationScope(machine=row.assigned_machine if row.assigned_machine_id else None,
                             machine_type=machine_type(row))


def version(row):
    return revision(row.status, row.updated_at, row.member_id, row.requester_id,
                    row.queue_id, row.bucket_id, row.assigned_machine_id)


def eligible(envelope):
    from .notifications_p2_service_notices import eligible as milestone_eligible, is_milestone
    if is_milestone(envelope):
        return milestone_eligible(envelope)
    row = rbac.scope_notification_policy(MachineServiceRequest.objects.all(),
        makerspace_id=envelope.makerspace_id).select_related(
        "requester", "member", "queue__machine_type", "bucket__machine__machine_type",
        "assigned_machine", "handled_by", "accepted_by", "collected_by",
    ).filter(pk=envelope.source_id).first()
    if row is None or version(row) != envelope.revision:
        return False
    expected = {"submitted": "pending", "started": "in_progress", "reprinted": "accepted"}.get(envelope.event, envelope.event)
    if row.status != expected or (envelope.event == "reprinted" and not row.reprint_of_id):
        return False
    if not module_enabled(envelope.makerspace, "machine_service") or not module_enabled(envelope.makerspace, "machines"):
        return False
    from .printer_capabilities import is_printer_type
    if is_printer_type(machine_type(row)) and not module_enabled(envelope.makerspace, "printing"):
        return False
    from . import access
    sender = row.requester if envelope.event == "submitted" else (
        row.accepted_by if envelope.event == "reprinted" else row.handled_by)
    if envelope.event == "cancelled":
        # A terminal, immutable fact authorized at mutation time by the owner or scoped
        # staff (C3); the recipient floor below still applies to every staff recipient.
        permitted = True
    elif sender is None:
        return False
    elif envelope.event == "collected":
        permitted = rbac.can(sender, rbac.Action.COLLECT_SERVICE_REQUEST, row.makerspace_id)
    elif envelope.event == "submitted":
        permitted = (sender.is_active and sender.access_status == "active"
                     and not sender.is_tenant_dump_stub and not sender.retired_at
                     and not sender.deletion_requested_at and not sender.account_purged_at)
    else:
        permitted = (access.can_operate_machine(sender, row.assigned_machine)
                     if row.assigned_machine_id else access.can_create_machine(sender, row.makerspace_id, machine_type(row)))
    if not permitted:
        return False
    if envelope.audience == "requester":
        from apps.hardware_requests.notifications_p2_email import source_ready
        return envelope.recipient_id == (row.member_id or row.requester_id) and source_ready(envelope)
    # The shared resolver checks recipient selection. This additional floor also
    # covers lifecycle alerts and explicitly selected staff with revoked type reach.
    if envelope.recipient_id:
        from apps.accounts.models import User
        recipient = User.objects.filter(pk=envelope.recipient_id).first()
        return recipient is not None and access.can_create_machine(recipient, row.makerspace_id, machine_type(row))
    return True


@safe_adapter
def notify_service(row, event):
    if event not in EVENTS:
        raise ValueError("Unknown machine service event")
    from .service_printing_emails import _projection, _is_printer_request
    link = local_link(row.makerspace, "member")
    staff_context = printing_context(_projection(row), "", "")
    if _is_printer_request(row) and event in {"submitted", "accepted", "rejected", "started", "completed"}:
        # Preserve authored printer templates; authenticated navigation replaces
        # bearer tracking credentials for all personal chat/native transports.
        context = {**staff_context, "status_url": link}
        own = content(render(row.makerspace, "printing", "requester", event,
                             context, machine_type=machine_type(row)), link=link)
        staff = content(render(row.makerspace, "printing", "staff", event,
                               context, machine_type=machine_type(row)))
    else:
        printer = _is_printer_request(row)
        v = {"id": row.pk, "event": event.replace("_", " ")}
        subject = (gettext("Print request #%(id)s") if printer else gettext("Machine service request #%(id)s")) % v
        own = {"subject": subject, "link": link,
               "text": (gettext("Your print request #%(id)s: %(event)s.") if printer
                        else gettext("Your machine service request #%(id)s: %(event)s.")) % v}
        staff = {"subject": subject,
                 "text": (gettext("Print request #%(id)s %(event)s.") if printer
                          else gettext("Machine service request #%(id)s %(event)s.")) % v}
    owner, own_content = row.member or row.requester, own
    if event in OWNER_MILESTONES:
        # Exactly-once owner intent keyed on the immutable marker; repeated calls are no-ops.
        from .service_queue_notices import initiator_for, reserve_milestone
        reserve_milestone(row, event, initiator=initiator_for(row.handled_by))
        owner = own_content = None
    # The fallback summary stays bounded; authored staff chat templates render separately.
    room_staff = dict(staff)
    room_staff["text"] = gettext("Machine service request #%(id)s %(event)s. Review in the staff console.") % {
        "id": row.pk, "event": event.replace("_", " ")}
    return fanout(space=row.makerspace, feature="printing", stream="printing", event=event,
        kind=KIND, source=row.pk, version=version(row), subject=row,
        owner=owner, own=own_content, staff=staff,
        room_body=room_staff["text"], staff_context=staff_context, scope=scope_for(row),
        context={"machine_service_request_id": row.pk})


def register():
    from .notifications_p2_service_notices import render_envelope
    register_source(KIND, NotificationSource(eligible, render_envelope))
