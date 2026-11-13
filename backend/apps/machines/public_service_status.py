"""Bearer-token status read for ANY machine-service job (printers included).

The generic intake returned a ``public_token`` with nowhere to use it; this closes that
gap. The token is a read capability only -- it never authorizes a write. The response
is an explicit PII-free allowlist (``PublicMachineServiceStatusSerializer``) plus the
shared ETA and counts from one request-scoped snapshot.
"""

from rest_framework.exceptions import NotFound

from apps.machines.models import MachineServiceRequest
from apps.machines.public_printer_service import _StatusProjection, status_context
from apps.makerspaces.servability import servable_queryset


def _machine_type(row):
    return row.queue.machine_type if row.queue_id else row.bucket.machine.machine_type


def public_service_status(public_token):
    """Return ``(projection, serializer_context)`` or raise 404/400 like the printer route."""
    row = servable_queryset(MachineServiceRequest.objects.select_related(
        "makerspace", "queue__machine_type", "bucket__machine__machine_type",
    ).filter(public_token=public_token), relation="makerspace").first()
    if row is None:
        raise NotFound()
    from apps.makerspaces.guards import require_module_for_servable

    machine_type = _machine_type(row)
    # The token names a job in ONE makerspace: that space's module and edition gates
    # apply (edition-hidden and module off both answer 404). Printer jobs need nothing more
    # since the `printing` module folded into machine service (340b).
    require_module_for_servable(row.makerspace, "machine_service")
    projection = _StatusProjection(row, printer=False)
    projection.machine_type_name = machine_type.name
    return projection, status_context([row])
