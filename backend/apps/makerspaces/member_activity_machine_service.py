"""The member's own machine-service rows for the activity dashboard, batched once.

Ownership is ``member_id`` only -- never contact fields or the historical ``requester``
FK. One query loads the member's recent rows and ONE request-scoped queue snapshot
serves both projections (``print_requests`` and ``machine_service_requests``); the
snapshot itself loads the full live workload of the relevant scopes, so the activity
limit never truncates the queue used to estimate these rows. Printer identity is the
resolved global type (``is_printer_type``), never a bare slug.
"""

ACTIVITY_LIMIT = 50


def _machine_type(row):
    return row.queue.machine_type if row.queue_id else row.bucket.machine.machine_type


def machine_service_activity(makerspace, member):
    """Return ``(print_requests, machine_service_requests)`` plain-dict rows."""
    from apps.machines.models import MachineServiceRequest
    from apps.machines.printer_capabilities import is_printer_type
    from apps.machines.service_queue_eta import queue_snapshot_for
    from apps.machines.service_queue_eta_serializers import ServiceRequestEtaSerializer
    from apps.machines.service_workflow_cancel import owner_may_cancel

    rows = list(MachineServiceRequest.objects.filter(
        makerspace_id=makerspace.pk, member=member,
    ).select_related(
        "makerspace", "queue__machine_type", "bucket__machine__machine_type",
    ).order_by("-created_at", "-id")[:ACTIVITY_LIMIT])
    snapshot = queue_snapshot_for(rows)
    from apps.makerspaces.platform import module_enabled
    service_enabled = module_enabled(makerspace, "machine_service")
    printers, services = [], []
    for row in rows:
        machine_type = _machine_type(row)
        printer = is_printer_type(machine_type)
        eta = snapshot.eta(row)
        counts = snapshot.counts(row) or {}
        common = {
            "request_id": row.pk, "public_token": row.public_token, "status": row.status,
            "title": row.title, "created_at": row.created_at, "cancelled_at": row.cancelled_at,
            "queue_position": counts.get("position"),
            "queue_approved_ahead": counts.get("approved_ahead"),
            "queue_awaiting_review_ahead": counts.get("awaiting_review_ahead"),
            "can_cancel": owner_may_cancel(row, member, service_enabled=service_enabled),
            "eta": ServiceRequestEtaSerializer(eta).data if eta is not None else None,
        }
        item = {**common, "machine_type_name": machine_type.name}
        if printer:
            item["machine_type"] = "3d_printer"
            printers.append({**common, "accepted_at": row.accepted_at, "started_at": row.started_at,
                             "completed_at": row.completed_at, "estimated_minutes": row.estimated_minutes})
        services.append(item)
    return printers, services
