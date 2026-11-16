import json
from types import SimpleNamespace

from apps.inventory.equipment_intent_v2 import proposal_fingerprint_from_snapshot
from apps.tenant_migration import pii_equipment_intent as subject
from apps.tenant_migration.insertion_errors import PrimaryKeyMapUnavailable


def setup_intent(monkeypatch):
    snapshot = {"version": 2, "makerspace_id": 1, "operation_id": "11111111-1111-4111-8111-111111111111", "original_borrower_id": 2, "original_creator_id": 7,
        "intent_kind": "self", "outcome_kind": "request", "event_registration_id": 3, "booking_id": 4, "waitlist_entry_id": 6,
        "product_ids": [5, 8], "kit": None, "content_sha256": "a" * 64}
    source = {"id": 11, "borrower_id": 2, "creator_id": 7, "operation_id": snapshot["operation_id"], "outcome_kind": "request", "intent_version": 2, "fingerprint_version": 2, "imported_nonreplayable": False, "payload_sha256": proposal_fingerprint_from_snapshot(snapshot)}
    model = SimpleNamespace(_meta=SimpleNamespace(db_table="receipt", pk=SimpleNamespace(attname="id", column="id")))
    monkeypatch.setattr(subject, "is_envelope", lambda _raw: True)
    monkeypatch.setattr(subject, "parse_envelope", lambda _raw: (1,))
    monkeypatch.setattr(subject, "decrypt_with_key_loader", lambda *_a, **_k: json.dumps(snapshot).encode())
    monkeypatch.setattr(subject, "encrypt", lambda plain, *_a, **_k: plain)
    return source, model


def test_rebinds_all_typed_ids_and_recomputes_digest(monkeypatch):
    source, model = setup_intent(monkeypatch)
    cipher, digest, unavailable = subject.rebind_equipment_intent(model, "envelope", source=source, row={"id": 21, "borrower_id": 102, "creator_id": 107}, source_id=1, target_id=101, deks={1: b"key"}, map_id=lambda _label, value: value + 100, creator_unavailable=False)
    result = json.loads(cipher)
    assert result["makerspace_id"] == 101 and result["original_borrower_id"] == 102
    assert result["event_registration_id"] == 103 and result["booking_id"] == 104
    assert result["product_ids"] == [105, 108] and result["original_creator_id"] == 107
    assert result["waitlist_entry_id"] == 106 and result["content_sha256"] == "a" * 64
    assert digest == proposal_fingerprint_from_snapshot(result) and not unavailable


def test_missing_domain_reference_yields_encrypted_unreplayable_tombstone(monkeypatch):
    source, model = setup_intent(monkeypatch)
    def mapper(label, value):
        if label == "events.EventRegistration":
            raise PrimaryKeyMapUnavailable("missing")
        return value + 100
    cipher, digest, unavailable = subject.rebind_equipment_intent(model, "envelope", source=source, row={"id": 21, "borrower_id": 102, "creator_id": 107}, source_id=1, target_id=101, deks={1: b"key"}, map_id=mapper, creator_unavailable=False)
    assert json.loads(cipher) == {"version": 2, "outcome_kind": "request", "unavailable": True}
    assert digest == "0" * 64 and unavailable


def test_tombstone_stays_unreplayable_even_if_old_numeric_ids_are_reused(monkeypatch):
    source, model = setup_intent(monkeypatch)
    source.update(imported_nonreplayable=True, payload_sha256="0" * 64)
    tombstone = {"version": 2, "outcome_kind": "request", "unavailable": True}
    monkeypatch.setattr(subject, "decrypt_with_key_loader", lambda *_a, **_k: json.dumps(tombstone).encode())
    def forbidden(*_args):
        raise AssertionError("A tombstone must never resolve selectors again")
    cipher, digest, unavailable = subject.rebind_equipment_intent(model, "envelope", source=source, row={"id": 21, "borrower_id": 102, "creator_id": 107}, source_id=1, target_id=101, deks={1: b"key"}, map_id=forbidden, creator_unavailable=False)
    assert json.loads(cipher) == tombstone and digest == "0" * 64 and unavailable


def test_missing_creator_produces_sticky_minimal_tombstone(monkeypatch):
    source, model = setup_intent(monkeypatch)
    cipher, digest, unavailable = subject.rebind_equipment_intent(model, "envelope", source=source, row={"id": 21, "borrower_id": 102, "creator_id": None}, source_id=1, target_id=101, deks={1: b"key"}, map_id=lambda _label, value: value + 100, creator_unavailable=True)
    assert json.loads(cipher) == {"version": 2, "outcome_kind": "request", "unavailable": True}
    assert digest == "0" * 64 and unavailable
