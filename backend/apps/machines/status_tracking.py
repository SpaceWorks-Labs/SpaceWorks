"""A status transition and its measured event commit together under the machine lock."""

from django.db import transaction

from apps.audit.services import record
from .models_tracking import MachineStatusEvent


@transaction.atomic
def change_status(machine, status, *, source, actor=None, extra_fields=(), reason="", expected_back_at=None):
    previous = machine.status
    machine.status = status
    machine.save(update_fields=["status", "updated_at", *extra_fields])
    if previous != status:
        MachineStatusEvent.objects.create(
            makerspace_id=machine.makerspace_id, machine=machine,
            from_status=previous, to_status=status, source=source,
        )
        record(actor, "machine.status_changed", makerspace=machine.makerspace, target=machine,
               meta={"old": previous, "new": status, "source": source})
        from .downtime import track
        track(machine, previous, status, actor=actor, reason=reason, expected_back_at=expected_back_at)
