"""Rebind nested DOB history using archive-custodied keys already in memory."""
from copy import deepcopy

from .pii_reencryption import reencrypt_mapped_value


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
