"""Validate and merge portable deletion fences without widening users.csv."""

from datetime import datetime

from apps.data_export.user_lifecycle import LIFECYCLE_FIELDS, LIFECYCLE_PATH

from .insertion_errors import ArchiveFormatError


def user_lifecycle(archive):
    # Older archives predate account deletion and have no lifecycle sidecar.
    if not (archive.root / LIFECYCLE_PATH).exists():
        return {}
    records = archive.json(LIFECYCLE_PATH)
    if not isinstance(records, dict):
        raise ArchiveFormatError("Invalid portable user lifecycle mapping.")
    for user_id, values in records.items():
        if not user_id.isdecimal() or not isinstance(values, dict) or set(values) != set(LIFECYCLE_FIELDS):
            raise ArchiveFormatError("Invalid portable user lifecycle fields.")
        for value in values.values():
            if not isinstance(value, str):
                raise ArchiveFormatError("Invalid portable user lifecycle timestamp.")
            if value:
                try:
                    parsed = datetime.fromisoformat(value)
                except ValueError as exc:
                    raise ArchiveFormatError("Invalid portable user lifecycle timestamp.") from exc
                if parsed.utcoffset() is None:
                    raise ArchiveFormatError("Portable user lifecycle timestamp lacks a timezone.")
    return records


def lifecycle_rows(archive, rows):
    records = user_lifecycle(archive)
    for row in rows:
        yield {**row, **records.pop(row["id"], {})}
    if records:
        raise ArchiveFormatError("Portable lifecycle names an identity outside users.csv.")
