import json
from types import SimpleNamespace

from apps.inventory.equipment_use_intent_v2 import use_fingerprint_from_snapshot
from apps.tenant_migration import pii_equipment_use_intent as subject


def data(monkeypatch):
    snapshot = {"version": 2, "makerspace_id": 1, "operation_id": "11111111-1111-4111-8111-111111111111", "original_creator_id": 2, "product_id": 3, "source_kind": "plan", "source_id": 4, "content_sha256": "a" * 64}
    source = {"id": 11, "creator_id": 2, "product_id": 3, "plan_id": 4, "allocation_id": None, "operation_id": snapshot["operation_id"], "intent_version": 2, "imported_nonreplayable": False, "payload_sha256": use_fingerprint_from_snapshot(snapshot)}
    model = SimpleNamespace(_meta=SimpleNamespace(db_table="receipt", pk=SimpleNamespace(attname="id", column="id")))
    monkeypatch.setattr(subject, "is_envelope", lambda _raw: True)
    monkeypatch.setattr(subject, "parse_envelope", lambda _raw: (1,))
    monkeypatch.setattr(subject, "decrypt_with_key_loader", lambda *_a, **_k: json.dumps(snapshot).encode())
    monkeypatch.setattr(subject, "encrypt", lambda plain, *_a, **_k: plain)
    return source, model


def test_use_intent_remaps_typed_refs_and_preserves_only_content_hash(monkeypatch):
    source, model = data(monkeypatch)
    cipher, digest, unavailable = subject.rebind_use_intent(model, "envelope", source=source, row={"id": 21, "creator_id": 102, "product_id": 103, "plan_id": 104}, source_id=1, target_id=101, deks={1: b"key"}, map_id=lambda _label, value: value + 100, creator_unavailable=False)
    result = json.loads(cipher)
    assert result["original_creator_id"] == 102 and result["product_id"] == 103 and result["source_id"] == 104
    assert result["content_sha256"] == "a" * 64 and "note" not in result and "quantity" not in result
    assert digest == use_fingerprint_from_snapshot(result) and not unavailable


def test_missing_creator_is_sticky_tombstone_without_source_identifiers(monkeypatch):
    source, model = data(monkeypatch)
    cipher, digest, unavailable = subject.rebind_use_intent(model, "envelope", source=source, row={"id": 21, "creator_id": None, "product_id": 103, "plan_id": 104}, source_id=1, target_id=101, deks={1: b"key"}, map_id=lambda _label, value: value + 100, creator_unavailable=True)
    assert json.loads(cipher) == {"version": 2, "unavailable": True}
    assert digest == "0" * 64 and unavailable
