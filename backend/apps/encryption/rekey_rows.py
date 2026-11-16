"""Row work for key jobs: re-encrypt envelopes to the new DEK, or re-index to the new search key.

Immutable programme history (``maintenance_programme.IMMUTABLE_LABELS``) and birth-date
source evidence are never rewritten here: their envelopes stay on the version that wrote
them, and that version stays unwrappable (it is retained, not disabled).
"""

from django.apps import apps
from django.db import DatabaseError, connection, transaction

from .crypto import PiiUnavailable, decrypt, encrypt, is_envelope, parse_envelope
from .maintenance_programme import IMMUTABLE_LABELS, MANDATORY_SOURCE_LABEL
from .models import MakerspaceEncryptionKey
from .models_rotation import KeyRotationJob
from .registry import fields_for_label, registered_labels


def _installed(label):
    try:
        apps.get_model(label)
    except LookupError:
        return False
    return True


def labels_for(kind):
    if kind == KeyRotationJob.Kind.SEARCH_REINDEX:
        return sorted(label for label in registered_labels() if _installed(label) and any(
            field.index_kind in {"bloom", "bloom_exact"} for field in fields_for_label(label)))
    return sorted(label for label in registered_labels()
                  if _installed(label) and label not in IMMUTABLE_LABELS and label != MANDATORY_SOURCE_LABEL)


def queryset_for(label, makerspace_id):
    model = apps.get_model(label)
    path = fields_for_label(label)[0].makerspace_path.replace(".", "__")
    return model._base_manager.filter(**{path: makerspace_id})


def space_keys(makerspace_id):
    """Every unwrappable DEK version of the space, loaded before any row transaction."""
    from .services import unwrap_dek
    rows = MakerspaceEncryptionKey.objects.filter(makerspace_id=makerspace_id).exclude(status="disabled")
    return {row.version: unwrap_dek(row) for row in rows}


def _rewrapped(row, label, makerspace_id, to_version, keys):
    updates = {}
    for field in fields_for_label(label):
        raw = row.__dict__.get(field.field_name)
        if not is_envelope(raw):
            continue
        version = parse_envelope(raw)[0]
        if version == to_version:
            continue
        aad = {"makerspace_id": makerspace_id, "table": row._meta.db_table, "pk": row.pk, "field": field.field_name}
        plaintext = decrypt(raw, keys[version], **aad)
        updates[row._meta.get_field(field.field_name).column] = encrypt(
            plaintext, keys[to_version], key_version=to_version, **aad)
    return updates


def reencrypt_rows(job, model, ids):
    from .write_fence import assert_mapped_write_allowed

    keys = space_keys(job.makerspace_id)
    if job.to_version not in keys:
        raise PiiUnavailable()
    label, done, skipped = model._meta.label, 0, 0
    with transaction.atomic():
        assert_mapped_write_allowed(job.makerspace_id)
        for row in model._base_manager.select_for_update().filter(pk__in=ids).order_by("pk"):
            try:
                updates = _rewrapped(row, label, job.makerspace_id, job.to_version, keys)
            except (KeyError, PiiUnavailable):
                skipped += 1  # a version this space can no longer unwrap: left as it is
                continue
            if not updates:
                continue
            assignments = ", ".join(f'"{column}" = %s' for column in updates)
            try:
                with transaction.atomic(), connection.cursor() as cursor:
                    cursor.execute(f'UPDATE "{row._meta.db_table}" SET {assignments} WHERE "{row._meta.pk.column}" = %s',
                                   [*updates.values(), row.pk])
                done += 1
            except DatabaseError:
                skipped += 1  # a guarded column (append-only table): retained on its old version
    return done, skipped


def reindex_rows(job, model, ids):
    from .blind_index import active_generation, upsert_index
    from .models import PiiBlindIndex
    from .search_keys import derive
    from .models_rotation import MakerspaceSearchKey

    salt = MakerspaceSearchKey.objects.get(makerspace_id=job.makerspace_id, version=job.to_version).salt
    space_key = (job.to_version, derive(job.makerspace_id, job.to_version, salt))
    generation = active_generation()
    label, done = model._meta.label, 0
    fields = [field for field in fields_for_label(label) if field.index_kind in {"bloom", "bloom_exact"}]
    current = set(PiiBlindIndex.objects.filter(
        makerspace_id=job.makerspace_id, model_label=label, object_id__in=ids,
        space_key_version=job.to_version, search_generation=generation,
    ).values_list("object_id", "field_name"))
    with transaction.atomic():
        for row in model._base_manager.select_for_update().filter(pk__in=ids).order_by("pk"):
            for field in fields:
                if (row.pk, field.field_name) in current:
                    continue
                upsert_index(row, field, getattr(row, field.field_name), generation, space_key=space_key)
            done += 1
    return done, 0
