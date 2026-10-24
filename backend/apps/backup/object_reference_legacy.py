"""Typed retention projection for the existing tenant/standalone object closure."""
from django.utils import timezone

from .object_reference_retention import adapter_for


def collect_retained(queryset, model, rule, ownership_paths, result, fixed_makerspace_id):
    adapter = adapter_for(rule)
    if adapter is None:
        return False
    owner_fields = [path if path in {"pk", "id"} else f"{path}_id" for path in ownership_paths]
    rows = queryset.values(*dict.fromkeys((rule.field_name, *owner_fields, *adapter.query_fields)))
    capture_at = timezone.now()
    for row in rows.iterator(chunk_size=500):
        key = row[rule.field_name]
        if not key:
            continue
        projection = adapter.project(row, capture_at)
        if not projection.capture:
            continue
        from .archive_objects import module_for_model
        ownership = {"makerspace_id": fixed_makerspace_id or next(
            (row[field] for field in owner_fields if row[field]), None),
            "module_key": module_for_model(model._meta.label)}
        if projection.expected_size_bytes is not None:
            ownership.update(expected_size_bytes=projection.expected_size_bytes,
                expected_sha256=projection.expected_sha256)
        if projection.retention_state == "expired":
            ownership.update(retention_state="expired",
                object_expired_at=projection.object_expired_at.isoformat(),
                expired_size_bytes=projection.expired_size_bytes)
        result[rule.bucket.value][str(key)] = ownership
    return True
