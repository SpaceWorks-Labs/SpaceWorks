"""Row insertion, the result record and the import fence for `materialization` (split out).

Re-exported from ``materialization``; import them from there.
"""

from dataclasses import dataclass

from apps.encryption.models import PiiMakerspaceWriteFence

from .raw_repository import RawImportRepository
from .row_planning import (
    final_row,
    protect_carried_unique_values,
    update_resolved_row,
)


@dataclass(frozen=True)
class MaterializationResult:
    target_makerspace_id: int
    imported: dict[str, int]
    resolved: dict[str, int]
    dropped: dict[str, int]
    preserved: dict[tuple[str, str], int]
    regenerated: dict[tuple[str, str], int]
    identities_linked: int
    identities_created: int
    preexisting_global_authority: tuple[dict[str, object], ...]
    installed_dek_versions: tuple[int, ...]
    blind_indexes_created: int
    external_references_created: int
    objects_staged: int
    object_keys_regenerated: int
    object_key_regenerations: dict[str, str]
    objects_promoted: int


def _report_for(result):
    return {
        "format_version": 1,
        "target_makerspace_id": result.target_makerspace_id,
        "imported": result.imported,
        "resolved": result.resolved,
        "dropped": result.dropped,
        "identities_linked": result.identities_linked,
        "identities_created": result.identities_created,
        "external_references_created": result.external_references_created,
    }


def _receipt_last(ordered):
    labels = {"inventory.EquipmentProposalReceipt", "inventory.EquipmentConsumableUseReceipt", "events.EventBookingDecision"}
    receipts = [model for model in ordered if model._meta.label in labels]
    if len(receipts) != 3 or {model._meta.label for model in receipts} != labels:
        raise ValueError("Equipment receipt models must each be present exactly once.")
    # Only this model is delayed. Refuse if a future exported model gains an
    # inbound FK: it would need its own reviewed insert-order treatment.
    for model in ordered:
        if model not in receipts and any(field.is_relation and field.related_model in receipts for field in model._meta.local_concrete_fields):
            raise ValueError("Equipment receipt has an unreviewed inbound dependency.")
    return [model for model in ordered if model not in receipts] + receipts


def _insert_models(
    ordered, archive, job, pk_map, references, target, deks,
    accounting, batch_size, object_key_map,
):
    repository = RawImportRepository()
    regenerated = set()
    from .import_pointers import PointerDeferral
    ordered = _receipt_last(ordered)
    pointers = PointerDeferral.begin(ordered)
    from .reference_state import EQUIPMENT_INTENT_LABELS
    for model in ordered:
        label = model._meta.label
        if label == "makerspaces.Makerspace":
            continue
        pending = []
        pending_equipment = []
        fresh_values = {}
        for source in pointers.source_rows(model, archive.rows(label)):
            if update_resolved_row(model, source, target):
                continue
            row = final_row(
                model,
                source,
                job=job,
                pk_map=pk_map,
                references=references,
                target=target,
                deks=deks,
                fresh_values=fresh_values,
                object_key_map=object_key_map,
            )
            if row is None:
                if label == "makerspaces.PublicHandle":
                    pk_map.discard_unmaterialized(model, source[model._meta.pk.attname])
                    accounting.increment("dropped", label)
                continue
            pointers.defer(model, row)
            for field_name, outcome in protect_carried_unique_values(
                model, row, target, fresh_values
            ):
                accounting.increment_field(outcome, label, field_name)
            pending.append(row)
            if label in EQUIPMENT_INTENT_LABELS:
                pending_equipment.append((source[model._meta.pk.attname], row[model._meta.pk.column]))
            if len(pending) == batch_size:
                inserted = repository.insert_rows(model, pending)
                if inserted != len(pending):
                    raise RuntimeError("Import batch did not insert every planned row.")
                accounting.increment("imported", label, inserted)
                if pending_equipment:
                    references.record_equipment_materialized(label, pending_equipment)
                regenerated.update((model, name) for _label, name in fresh_values)
                pending.clear()
                pending_equipment.clear()
                fresh_values.clear()
        if pending:
            inserted = repository.insert_rows(model, pending)
            if inserted != len(pending):
                raise RuntimeError("Import batch did not insert every planned row.")
            accounting.increment("imported", label, inserted)
            if pending_equipment:
                references.record_equipment_materialized(label, pending_equipment)
            regenerated.update((model, name) for _label, name in fresh_values)
    pointers.apply()
    return regenerated


def _close_target_import_fence(target, operation_id):
    updated = PiiMakerspaceWriteFence.objects.filter(
        makerspace=target,
        state=PiiMakerspaceWriteFence.State.OPEN,
    ).update(
        state=PiiMakerspaceWriteFence.State.CLOSED,
        operation_id=operation_id,
        operation_kind=PiiMakerspaceWriteFence.OperationKind.TENANT_IMPORT,
    )
    if updated != 1:
        raise RuntimeError("The target tenant import fence could not be closed.")
