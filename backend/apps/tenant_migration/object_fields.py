"""Rewrite portable object references to their preassigned target keys."""

from .insertion_errors import ArchiveFormatError


PRIVATE_FIELDS = frozenset({"object_key"})
PUBLIC_FIELDS = frozenset({"image_key", "avatar_key", "logo_key", "cover_image_key"})
OBJECT_FIELDS = PRIVATE_FIELDS | PUBLIC_FIELDS


def rewrite_object_fields(model, row, object_key_map):
    for field in model._meta.local_concrete_fields:
        if field.name not in OBJECT_FIELDS:
            continue
        source_key = row.get(field.column)
        if not source_key:
            continue
        try:
            row[field.column] = object_key_map[str(source_key)]
        except KeyError as exc:
            raise ArchiveFormatError(
                f"Archive object manifest does not account for {source_key!r}."
            ) from exc
    if model._meta.label == "events.EventAttendanceCertificate":
        _rewrite_certificate_snapshot(row, object_key_map)


def _rewrite_certificate_snapshot(row, object_key_map):
    snapshot = row.get("layout_snapshot")
    if not isinstance(snapshot, dict):
        raise ArchiveFormatError("Certificate layout snapshot must be an object.")
    source_key = snapshot.get("artwork_object_key")
    if not source_key:
        return
    if not isinstance(source_key, str) or source_key not in object_key_map:
        raise ArchiveFormatError("Certificate artwork snapshot is absent from the object manifest.")
    # S3 version ids are local to the source bucket. The SHA-256 remains the
    # immutable byte identity after target promotion creates a different version.
    row["layout_snapshot"] = {
        **snapshot, "artwork_object_key": object_key_map[source_key],
        "artwork_version_id": "",
    }


def bucket_kind_for_field(field_name):
    if field_name in PRIVATE_FIELDS:
        return "private"
    if field_name in PUBLIC_FIELDS:
        return "public_image"
    return None
