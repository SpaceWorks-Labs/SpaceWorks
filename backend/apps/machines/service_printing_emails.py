"""Printing-branded lifecycle delivery for kernel 3D-printer requests."""

import logging
from types import SimpleNamespace
from urllib.parse import urlencode

from apps.integrations.email_templates import printing_context, render
from apps.machines.printer_capabilities import is_printer_type
from apps.makerspaces.website_directory import public_url

logger = logging.getLogger(__name__)
REQUESTER_EVENTS = frozenset({"submitted", "accepted", "started", "rejected", "completed", "failed", "collected", "reprinted"})


def _request_machine_type(request):
    return request.queue.machine_type if request.queue_id else request.bucket.machine.machine_type


def _is_printer_request(request):
    return is_printer_type(_request_machine_type(request))


def _projection(request):
    payload = request.capability_payload or {}
    status = "printing" if request.status == request.Status.IN_PROGRESS else request.status
    makerspace = request.makerspace
    queue_name = request.queue.name if request.queue_id else request.bucket.name
    return SimpleNamespace(
        id=request.pk, status=status, title=request.title, reason=request.reason,
        material=payload.get("requested_material", ""), color=payload.get("requested_color", ""),
        quantity=payload.get("quantity", 1), requester_name=request.requester_name,
        contact_email=request.contact_email, contact_phone=request.contact_phone,
        reprint_of_id=request.reprint_of_id, requester=request.requester,
        bucket=SimpleNamespace(name=queue_name, makerspace=makerspace),
    )


def _requester_render(event, request):
    recipient = request.contact_email or request.requester.email
    if not recipient:
        return None, None
    status_url = public_url(request.makerspace, "print", "").rstrip("/") + "?" + urlencode({"token": request.public_token})
    row = _projection(request)
    return recipient, render(
        request.makerspace,
        "printing",
        "requester",
        event,
        printing_context(row, status_url, request.public_token),
        machine_type=_request_machine_type(request),
    )


def _staff_render(event, request):
    return render(
        request.makerspace,
        "printing",
        "staff",
        event,
        printing_context(_projection(request), "", ""),
        machine_type=_request_machine_type(request),
    )


def _staff_body(event, request):
    row = _projection(request)
    lines = [
        f"Print request #{row.id} {event}.", "", f"Status: {row.status}",
        f"Title: {row.title}", f"Requester: {row.requester_name or row.requester.username}",
    ]
    if row.contact_email or row.requester.email:
        lines.append(f"Email: {row.contact_email or row.requester.email}")
    if row.contact_phone:
        lines.append(f"Phone: {row.contact_phone}")
    if row.material:
        lines.append(f"Material: {row.material}")
    if row.color:
        lines.append(f"Color: {row.color}")
    lines.append(f"Quantity: {row.quantity}")
    if row.reason:
        lines.append(f"Reason: {row.reason}")
    return "\n".join(lines)


def notify_printer_service_status(request, event, *, sync=False):
    """Use the established printing template and mute matrix for kernel work."""
    if not _is_printer_request(request):
        return None
    from .notifications_p2_service import notify_service
    return notify_service(request, event)
