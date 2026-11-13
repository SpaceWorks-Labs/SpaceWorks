"""Rebind consumable-use intent before its immutable receipt is inserted."""
import hmac
import json

from django.core.exceptions import ValidationError
from apps.encryption.crypto import decrypt_with_key_loader, encrypt, is_envelope, parse_envelope
from apps.inventory.equipment_use_intent_v2 import canonical_use_intent_json, use_fingerprint_from_snapshot
from .insertion_errors import ArchiveFormatError, PrimaryKeyMapUnavailable


def rebind_use_intent(model, raw, *, source, row, source_id, target_id, deks, map_id, creator_unavailable):
    if not is_envelope(raw) or source["intent_version"] != 2:
        raise ArchiveFormatError("Unsupported consumable use intent.")
    version = parse_envelope(raw)[0]
    plain = decrypt_with_key_loader(raw, makerspace_id=source_id, table=model._meta.db_table,
        pk=source[model._meta.pk.attname], field="intent_snapshot", load_dek=lambda v: deks[v])
    tombstone = {"version": 2, "unavailable": True}
    try:
        snapshot = json.loads(plain)
        if source["imported_nonreplayable"]:
            if snapshot != tombstone or source["payload_sha256"] != "0" * 64:
                raise ArchiveFormatError("Invalid unavailable use intent.")
            encoded, digest, unavailable = json.dumps(tombstone, sort_keys=True, separators=(",", ":")), "0" * 64, True
        else:
            canonical_use_intent_json(snapshot)
            if not hmac.compare_digest(use_fingerprint_from_snapshot(snapshot), source["payload_sha256"]):
                raise ArchiveFormatError("Use intent digest does not match.")
            kind = snapshot["source_kind"]
            if (snapshot["makerspace_id"] != source_id or snapshot["operation_id"] != str(source["operation_id"])
                    or snapshot["original_creator_id"] != source["creator_id"] or snapshot["product_id"] != source["product_id"]
                    or snapshot["source_id"] != source[f"{kind}_id"]):
                raise ArchiveFormatError("Use intent does not match its required receipt fields.")
            try:
                if creator_unavailable:
                    raise PrimaryKeyMapUnavailable("Historical creator was not retained.")
                snapshot["makerspace_id"] = target_id
                snapshot["original_creator_id"] = row["creator_id"]
                snapshot["product_id"] = map_id("inventory.InventoryProduct", snapshot["product_id"])
                source_label = "inventory.EquipmentKitAllocation" if kind == "allocation" else "inventory.EquipmentConsumablePlan"
                snapshot["source_id"] = map_id(source_label, snapshot["source_id"])
                if snapshot["product_id"] != row["product_id"] or snapshot["source_id"] != row[f"{kind}_id"]:
                    raise ArchiveFormatError("Use intent does not match its mapped required fields.")
                encoded = canonical_use_intent_json(snapshot)
                digest, unavailable = use_fingerprint_from_snapshot(snapshot), False
            except (LookupError, PrimaryKeyMapUnavailable):
                encoded, digest, unavailable = json.dumps(tombstone, sort_keys=True, separators=(",", ":")), "0" * 64, True
    except (TypeError, ValueError, UnicodeError, ValidationError) as exc:
        raise ArchiveFormatError("Invalid consumable use intent.") from exc
    ciphertext = encrypt(encoded.encode("utf-8"), deks[version], key_version=version,
        makerspace_id=target_id, table=model._meta.db_table, pk=row[model._meta.pk.column], field="intent_snapshot")
    return ciphertext, digest, unavailable
