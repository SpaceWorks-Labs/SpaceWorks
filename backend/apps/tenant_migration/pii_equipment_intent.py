"""Rebind a receipt's encrypted canonical intent during tenant import."""
import json
import hmac

from django.core.exceptions import ValidationError
from apps.encryption.crypto import decrypt_with_key_loader, encrypt, is_envelope, parse_envelope
from apps.inventory.equipment_intent_v2 import canonical_intent_json, proposal_fingerprint_from_snapshot
from .insertion_errors import ArchiveFormatError, PrimaryKeyMapUnavailable


def rebind_equipment_intent(model, raw, *, source, row, source_id, target_id, deks, map_id, creator_unavailable):
    """Return target ciphertext, digest and nonreplayable flag; never persist raw source IDs."""
    if not is_envelope(raw):
        raise ArchiveFormatError("Equipment intent is not an encrypted envelope.")
    if source["intent_version"] != 2 or source["fingerprint_version"] != 2:
        raise ArchiveFormatError("Unsupported equipment intent version.")
    version = parse_envelope(raw)[0]
    plain = decrypt_with_key_loader(raw, makerspace_id=source_id, table=model._meta.db_table,
        pk=source[model._meta.pk.attname], field="intent_snapshot", load_dek=lambda v: deks[v])
    tombstone = {"version": 2, "outcome_kind": source["outcome_kind"], "unavailable": True}
    try:
        snapshot = json.loads(plain)
        if source["imported_nonreplayable"]:
            if snapshot != tombstone or source["payload_sha256"] != "0" * 64:
                raise ArchiveFormatError("Invalid unavailable equipment intent.")
            encoded = json.dumps(tombstone, sort_keys=True, separators=(",", ":"))
            ciphertext = encrypt(encoded.encode("utf-8"), deks[version], key_version=version,
                makerspace_id=target_id, table=model._meta.db_table, pk=row[model._meta.pk.column], field="intent_snapshot")
            return ciphertext, "0" * 64, True
        canonical_intent_json(snapshot)
        if not hmac.compare_digest(proposal_fingerprint_from_snapshot(snapshot), source["payload_sha256"]):
            raise ArchiveFormatError("Equipment intent digest does not match.")
    except (TypeError, ValueError, UnicodeError, ValidationError) as exc:
        raise ArchiveFormatError("Invalid equipment intent.") from exc
    if (snapshot["makerspace_id"] != source_id or snapshot["original_borrower_id"] != source["borrower_id"] or snapshot["original_creator_id"] != source["creator_id"]
            or snapshot["operation_id"] != str(source["operation_id"]) or snapshot["outcome_kind"] != source["outcome_kind"]):
        raise ArchiveFormatError("Equipment receipt intent does not match its owner.")
    try:
        if creator_unavailable:
            raise PrimaryKeyMapUnavailable("Historical creator was not retained.")
        snapshot["makerspace_id"] = target_id
        # The receipt's required borrower FK was independently resolved by the
        # importer. It is not eligible for the optional-history fallback.
        snapshot["original_borrower_id"] = row["borrower_id"]
        snapshot["original_creator_id"] = row["creator_id"]
        for field, label in (("event_registration_id", "events.EventRegistration"), ("booking_id", "bookings.Booking"), ("waitlist_entry_id", "hardware_requests.LoanWaitlistEntry")):
            if snapshot[field] is not None:
                snapshot[field] = map_id(label, snapshot[field])
        if snapshot["product_ids"] is not None:
            snapshot["product_ids"] = [map_id("inventory.InventoryProduct", item) for item in snapshot["product_ids"]]
        else:
            snapshot["kit"]["id"] = map_id("inventory.EquipmentKitTemplate", snapshot["kit"]["id"])
        encoded = canonical_intent_json(snapshot)
        digest = proposal_fingerprint_from_snapshot(snapshot)
        nonreplayable = False
    except (LookupError, PrimaryKeyMapUnavailable):
        encoded = json.dumps(tombstone, sort_keys=True, separators=(",", ":"))
        digest, nonreplayable = "0" * 64, True
    ciphertext = encrypt(encoded.encode("utf-8"), deks[version], key_version=version,
        makerspace_id=target_id, table=model._meta.db_table, pk=row[model._meta.pk.column], field="intent_snapshot")
    return ciphertext, digest, nonreplayable
