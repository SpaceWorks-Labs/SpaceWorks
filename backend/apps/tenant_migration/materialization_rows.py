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


def _insert_models(
    ordered, archive, job, pk_map, references, target, deks,
    accounting, batch_size, object_key_map,
):
    repository = RawImportRepository()
    regenerated = set()
    from .import_pointers import PointerDeferral
    pointers = PointerDeferral.begin(ordered)
    for model in ordered:
        label = model._meta.label
        if label == "makerspaces.Makerspace":
            continue
        pending = []
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
            if len(pending) == batch_size:
                accounting.increment(
                    "imported", label, repository.insert_rows(model, pending)
                )
                regenerated.update((model, name) for _label, name in fresh_values)
                pending.clear()
                fresh_values.clear()
        if pending:
            accounting.increment(
                "imported", label, repository.insert_rows(model, pending)
            )
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
