"""Machine-service parity on the existing printing notification category."""
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
EVENTS = {"submitted", "accepted", "rejected", "started", "completed", "failed", "collected", "reprinted"}


def machine_type(row):
    return row.queue.machine_type if row.queue_id else row.bucket.machine.machine_type


def scope_for(row):
    return NotificationScope(machine=row.assigned_machine if row.assigned_machine_id else None,
                             machine_type=machine_type(row))


def version(row):
    return revision(row.status, row.updated_at, row.member_id, row.requester_id,
                    row.queue_id, row.bucket_id, row.assigned_machine_id)


def eligible(envelope):
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
    if sender is None:
        return False
    if envelope.event == "collected":
        permitted = rbac.can(sender, rbac.Action.COLLECT_SERVICE_REQUEST, row.makerspace_id)
    elif envelope.event == "submitted":
        permitted = sender.is_active and sender.access_status == "active"
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
    if _is_printer_request(row) and event in {"submitted", "accepted", "rejected", "started", "completed"}:
        # Preserve authored printer templates; authenticated navigation replaces
        # bearer tracking credentials for all personal chat/native transports.
        context = printing_context(_projection(row), link, "")
        own = content(render(row.makerspace, "printing", "requester", event,
                             context, machine_type=machine_type(row)), link=link)
        staff = content(render(row.makerspace, "printing", "staff", event,
                               context, machine_type=machine_type(row)))
    else:
        label = "Print" if _is_printer_request(row) else "Machine service"
        own = {"subject": f"{label} request #{row.pk}",
               "text": f"Your {label.lower()} request #{row.pk}: {event.replace('_', ' ')}.", "link": link}
        staff = {"subject": f"{label} request #{row.pk}",
                 "text": f"{label} request #{row.pk} {event.replace('_', ' ')}."}
    # Room summaries never inherit requester templates, contacts, reasons or links.
    room_staff = dict(staff)
    room_staff["text"] = f"Machine service request #{row.pk} {event.replace('_', ' ')}. Review in the staff console."
    return fanout(space=row.makerspace, feature="printing", stream="printing", event=event,
        kind=KIND, source=row.pk, version=version(row), subject=row,
        owner=row.member or row.requester, own=own, staff=staff,
        room_body=room_staff["text"], scope=scope_for(row),
        context={"machine_service_request_id": row.pk})


def register():
    register_source(KIND, NotificationSource(eligible))
