"""Core equipment records, after optional domain plan links have been removed.

Call only from the existing authorized whole-tenant purge transaction. PROTECT
remains active: a missed link must abort the purge rather than erase another
tenant's records. This helper must run before hardware requests are deleted.
"""
from .models_equipment_proposals import (
    EquipmentConsumablePlan, EquipmentConsumableUseReceipt, EquipmentKitAllocation, EquipmentKitTemplate,
    EquipmentKitVersion, EquipmentProposalReceipt,
)
from django.db import connection


def _delete_guarded(queryset, makerspace_id):
    model = queryset.model
    # The tenant purge owns the maker lock and transaction. Each delete receives
    # only its exact row/table/maker permit; no general immutable-delete flag.
    for pk in queryset.values_list("pk", flat=True).iterator(chunk_size=200):
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('app.equipment_purge_model', %s, true), set_config('app.equipment_purge_id', %s, true), set_config('app.equipment_purge_makerspace', %s, true)", [model._meta.db_table, str(pk), str(makerspace_id)])
        try:
            queryset.filter(pk=pk).delete()
        finally:
            # On database failure the transaction rolls back and local settings
            # disappear; do not mask that failure with another SQL statement.
            if not connection.needs_rollback:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT set_config('app.equipment_purge_model', '', true), set_config('app.equipment_purge_id', '', true), set_config('app.equipment_purge_makerspace', '', true)")


def delete_equipment_use_receipts(makerspace):
    if not connection.in_atomic_block:
        raise RuntimeError("Equipment purge requires the authorized tenant transaction.")
    _delete_guarded(EquipmentConsumableUseReceipt.objects.filter(makerspace=makerspace), makerspace.pk)


def delete_equipment_proposals(makerspace):
    if not connection.in_atomic_block:
        raise RuntimeError("Equipment purge requires the authorized tenant transaction.")
    _delete_guarded(EquipmentProposalReceipt.objects.filter(makerspace=makerspace), makerspace.pk)
    _delete_guarded(EquipmentKitAllocation.objects.filter(makerspace=makerspace), makerspace.pk)
    _delete_guarded(EquipmentConsumablePlan.objects.filter(makerspace=makerspace), makerspace.pk)
    _delete_guarded(EquipmentKitVersion.objects.filter(template__makerspace=makerspace), makerspace.pk)
    EquipmentKitTemplate.objects.filter(makerspace=makerspace).delete()
