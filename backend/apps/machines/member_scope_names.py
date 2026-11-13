"""Id-to-name lookups so scope responses carry labels for the role editor."""

from .models import Machine, MachineType


def named_machine_types(ids):
    rows = MachineType.objects.filter(pk__in=list(ids or ())).order_by("name", "id")
    return [{"id": row.pk, "name": row.name} for row in rows]


def named_machines(ids):
    rows = Machine.objects.filter(pk__in=list(ids or ())).order_by("name", "id")
    return [{"id": row.pk, "name": row.name, "machine_type_id": row.machine_type_id} for row in rows]
