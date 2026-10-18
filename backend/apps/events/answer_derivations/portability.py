"""Ciphertext fidelity adapter for G's source-fenced tenant archive/import path."""

from copy import deepcopy

from apps.accounts.saved_details.age import validate_dob
from apps.encryption.crypto import decrypt_with_key_loader

from .crypto import encrypt_source, prepared_key, require_preparation_boundary
from .models import EventAnswerDerivation

PORTABLE_FIELDS = (
    "id", "event_id", "registration_id", "application_id", "role_assignment_id", "question_id",
    "source_dob_envelope", "event_date_revision", "as_of_date", "locked_at", "version", "source_history",
)


def remap_canonical_answers(document, map_id):
    """Remap F's discriminated descriptors, never recurse through user values.

    v1 maps have no typed references. A v2 age descriptor carries evidence, not
    a numeric age; an asset reference names an independently event-owned resume.
    """
    result = deepcopy(document)
    if not isinstance(result, dict) or result.get("version") != 2:
        return result
    if not {"form_id", "form_revision", "answers"} <= result.keys():
        return result  # A legacy question may itself be named "version".
    if not isinstance(result["answers"], list):
        raise ValueError("Invalid canonical answer document.")
    for answer in result["answers"]:
        if not isinstance(answer, dict) or not {"id", "type"} <= answer.keys():
            raise ValueError("Invalid canonical answer descriptor.")
        if answer["type"] == "age_at_event":
            if "value" in answer or "derivation_id" not in answer:
                raise ValueError("An age answer must retain its source reference only.")
            answer["derivation_id"] = _reference("events.EventAnswerDerivation", answer["derivation_id"], map_id)
        elif answer["type"] == "asset_reference":
            value = answer.get("value")
            if not isinstance(value, dict) or set(value) != {"asset_id", "sha256"}:
                raise ValueError("Invalid canonical asset descriptor.")
            value["asset_id"] = _reference("events.HackathonParticipantAsset", value["asset_id"], map_id)
    return result


def _reference(label, value, map_id):
    if type(value) is not int or value <= 0:
        raise ValueError("Invalid typed answer reference.")
    return map_id(label, value)


def capture_event_sources(*, event_id):
    """Canonical tenant evidence only. The global vault/key registry is not read.

    G owns archive authorization, source gates and the consistent capture boundary.
    Date values use the archive writer's existing typed date encoder.
    """
    return EventAnswerDerivation.objects.filter(event_id=event_id).order_by("pk").values(*PORTABLE_FIELDS)


def rebind_portable_envelopes(
    record, *, source_makerspace_id, target_makerspace_id, target_pk, source_key_loader,
):
    """Prepare rebinding before import locks; G separately remaps typed FK IDs.

    The source loader belongs to the verified archive's tenant key custody. The
    target uses an already-ready host key. Every history envelope authenticates
    against its original row/field and is re-encrypted against the target row.
    Plain DOB/reason values exist only in this function's temporary memory.
    """
    require_preparation_boundary()
    if not isinstance(record, dict) or set(record) != set(PORTABLE_FIELDS):
        raise ValueError("Use a complete typed derivation archive record.")
    if any(type(value) is not int or value <= 0 for value in (
        source_makerspace_id, target_makerspace_id, target_pk, record["id"],
    )):
        raise ValueError("Use verified tenant and row IDs.")
    if sum(record[f"{name}_id"] is not None for name in (
        "registration", "application", "role_assignment",
    )) != 1:
        raise ValueError("Bind exactly one typed archive subject.")
    history = record["source_history"]
    history_keys = {"source_dob_envelope", "event_date_revision", "as_of_date", "locked_at", "version", "reason_envelope"}
    if not isinstance(history, list) or any(
        not isinstance(snapshot, dict) or set(snapshot) != history_keys for snapshot in history
    ):
        raise ValueError("Use typed encrypted history snapshots.")
    version, dek = prepared_key(target_makerspace_id)
    result = deepcopy(record)

    def rebind(raw, field):
        plaintext = decrypt_with_key_loader(
            raw, makerspace_id=source_makerspace_id, table=EventAnswerDerivation._meta.db_table,
            pk=record["id"], field=field, load_dek=source_key_loader,
        ).decode("utf-8")
        if field == "source_dob_envelope":
            validate_dob(plaintext)
        elif not plaintext.strip() or len(plaintext) > 1000:
            raise ValueError("Use a bounded encrypted reopening reason.")
        return encrypt_source(
            plaintext, pk=target_pk, makerspace_id=target_makerspace_id,
            version=version, dek=dek, field=field,
        )

    result["source_dob_envelope"] = rebind(record["source_dob_envelope"], "source_dob_envelope")
    for snapshot in result["source_history"]:
        snapshot["source_dob_envelope"] = rebind(snapshot["source_dob_envelope"], "source_dob_envelope")
        snapshot["reason_envelope"] = rebind(snapshot["reason_envelope"], "reopen_reason_envelope")
    result["id"] = target_pk
    return result
