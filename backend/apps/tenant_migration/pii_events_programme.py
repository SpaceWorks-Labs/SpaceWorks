"""Rebind nested DOB history using archive-custodied keys already in memory."""
from copy import deepcopy
import json

from apps.encryption.crypto import decrypt_with_key_loader, encrypt, is_envelope, parse_envelope

from .pii_reencryption import reencrypt_mapped_value

ANSWER_FIELDS = {
    ("events.EventRegistration", "custom_answers"),
    ("events.HackathonApplication", "answers_snapshot"),
    ("events.HackathonApplicationAnswerRevision", "answers_snapshot"),
    ("events.EventRoleAssignment", "answers"),
    ("events.EventRoleAnswerRevision", "answers"),
    ("events.MentorRoundCheckin", "answers"),
    ("events.HackathonSubmission", "form_answers"),
}


def rebind_programme_document(model, name, raw, *, source, row, target_id, source_id, deks, map_id):
    """Use archive-custodied keys only; no KMS or target key provisioning here."""
    label = model._meta.label
    snapshot = (label, name) == ("events.SubmissionSnapshot", "project")
    if not snapshot and (label, name) not in ANSWER_FIELDS:
        return None
    from apps.events.answer_derivations.portability import remap_canonical_answers
    from apps.events.submissions.portability import remap_snapshot
    envelope = is_envelope(raw)
    if envelope:
        version = parse_envelope(raw)[0]
        plain = decrypt_with_key_loader(raw, makerspace_id=source_id, table=model._meta.db_table,
            pk=source["id"], field=name, load_dek=lambda v: deks[v]).decode("utf-8")
    else:
        plain = raw
        if not deks:
            raise ValueError("Private programme documents require archive-custodied keys.")
        version = max(deks)
    document = json.loads(plain) if isinstance(plain, str) else plain
    if snapshot:
        if isinstance(source.get("project"), dict):
            document = source["project"]
        # ``source`` is the raw CSV row (JSON columns are text); ``row`` holds coerced values.
        members = row.get("sealed_member_ids", source.get("sealed_member_ids"))
        if isinstance(members, str):
            members = json.loads(members)
        remapped = remap_snapshot(project=document, sealed_member_ids=members,
            source_hash=source.get("source_content_sha256") or source["content_sha256"], map_id=map_id)
        document = remapped.pop("project")
        row.update(remapped)
    else:
        document = remap_canonical_answers(document, map_id)
    plain = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    rebound = encrypt(plain.encode(), deks[version], key_version=version,
        makerspace_id=target_id, table=model._meta.db_table, pk=row["id"], field=name)
    return rebound, plain


def rebind_derivation_history(model, source, row, *, source_makerspace_id, target_makerspace_id, deks):
    if model._meta.label != "events.EventAnswerDerivation":
        return
    history = deepcopy(row["source_history"])
    expected = {"source_dob_envelope", "event_date_revision", "as_of_date", "locked_at", "version", "reason_envelope"}
    if not isinstance(history, list) or any(not isinstance(item, dict) or set(item) != expected for item in history):
        raise ValueError("Invalid encrypted derivation history.")
    for item in history:
        for key, aad_field in (("source_dob_envelope", "source_dob_envelope"), ("reason_envelope", "reopen_reason_envelope")):
            if not item[key]:
                raise ValueError("Missing encrypted derivation evidence.")
            item[key] = reencrypt_mapped_value(item[key], source_aad={
                "makerspace_id": source_makerspace_id, "table": model._meta.db_table,
                "pk": source["id"], "field": aad_field,
            }, target_makerspace_id=target_makerspace_id, target_table=model._meta.db_table,
                target_pk=row["id"], target_field=aad_field, deks=deks)
    row["source_history"] = history
