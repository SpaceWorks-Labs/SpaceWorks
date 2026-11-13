"""Printing's domain adapter, shared without importing optional inbox models."""
from types import SimpleNamespace


def printing_projection(request):
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
