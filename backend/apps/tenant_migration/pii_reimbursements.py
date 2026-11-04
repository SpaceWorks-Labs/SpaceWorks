"""Rebind encrypted reimbursement/stage/payout documents that carry typed IDs.

The archive keeps these values as source ciphertext. Here, inside the import
transaction and with archive-custodied keys only, each one is authenticated under
its source AAD, its typed reference slots are remapped by the owning package's
transform, and it is sealed again under the target AAD with the same key version.
Plaintext exists only in memory; nothing is logged or written outside the row.
"""
import json

from apps.encryption.crypto import decrypt_with_key_loader, encrypt, is_envelope, parse_envelope

DOCUMENTS = frozenset({
    ("event_reimbursements.GrantRequest", "estimated_cost"),
    ("event_reimbursements.GrantRequest", "eligibility_snapshot"),
    ("event_reimbursements.ReimbursementClaim", "draft_payload"),
    ("events.StageFormResponse", "answers_snapshot"),
    ("events.StageFormResponseRevision", "answers_snapshot"),
    ("payments.EventPayoutObligationRevision", "decision_summary"),
})


def _transform(label, name, plain, map_id, map_uuid):
    if label.startswith("event_reimbursements."):
        from apps.event_reimbursements.portable import remap_structured
        return remap_structured(label.split(".", 1)[1], name, plain,
                                lambda target, value: map_id(target, value))
    document = json.loads(plain)
    if label.startswith("events."):
        from apps.events.staged_forms.portable import remap_json
        document = remap_json(f"{label}.{name}", document, map_id=map_id)
    else:
        from apps.payments.event_payouts.portable import remap_summary
        document = remap_summary(document, map_id=map_id, map_uuid=map_uuid)
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def rebind_reimbursement_document(model, name, raw, *, source, row, target_id, source_id, deks, map_id):
    label = model._meta.label
    if (label, name) not in DOCUMENTS or raw in (None, ""):
        return None
    from .semantic_reimbursements import uuid_mapper
    if is_envelope(raw):
        version = parse_envelope(raw)[0]
        plain = decrypt_with_key_loader(raw, makerspace_id=source_id, table=model._meta.db_table,
            pk=source[model._meta.pk.attname], field=name, load_dek=lambda v: deks[v]).decode("utf-8")
    else:
        if not deks:
            raise ValueError("Private reimbursement documents require archive-custodied keys.")
        version, plain = max(deks), raw
    if plain in ("", "{}"):
        remapped = plain
    else:
        remapped = _transform(label, name, plain, map_id, uuid_mapper(map_id))
    rebound = encrypt(remapped.encode(), deks[version], key_version=version, makerspace_id=target_id,
        table=model._meta.db_table, pk=row[model._meta.pk.column], field=name)
    return rebound, remapped
