from copy import deepcopy
from types import SimpleNamespace

import pytest
from django.core.exceptions import ValidationError

from apps.inventory.equipment_intent_v2 import (
    canonical_intent_json, make_proposal_intent, proposal_fingerprint_from_snapshot,
)
from apps.inventory.equipment_proposal_receipts import receipt_matches
from apps.inventory.equipment_use_intent_v2 import make_use_intent, use_fingerprint_from_snapshot

OPERATION = "381091a1-0f99-4d3f-9464-55f40986864e"


def proposal(**changes):
    data = dict(makerspace_id=1, operation_id=OPERATION, original_borrower_id=4,
                original_creator_id=5, intent_kind="staff", outcome_kind="request",
                event_registration_id=7, booking_id=8,
                request_fields={"items": [{"product_id": 2, "quantity": 1},
                                          {"product_id": 9, "quantity": 3}],
                                "requested_for": "private purpose", "pickup_from": None})
    data.update(changes)
    return make_proposal_intent(**data)


def test_remap_preserves_product_ordinal_even_when_target_ids_reverse_order():
    source = proposal()
    remapped = deepcopy(source)
    remapped.update(makerspace_id=11, original_borrower_id=14, original_creator_id=15,
                    event_registration_id=17, booking_id=18, product_ids=[90, 20])
    assert remapped["content_sha256"] == source["content_sha256"]
    assert proposal_fingerprint_from_snapshot(source) != proposal_fingerprint_from_snapshot(remapped)
    assert "private purpose" not in canonical_intent_json(source)


@pytest.mark.parametrize("field,value", [
    ("requested_for", "different"), ("pickup_from", "2026-11-09T10:00:00Z"),
    ("pickup_until", "2026-11-10T10:00:00Z"),
    ("items", [{"product_id": 2, "quantity": 2}, {"product_id": 9, "quantity": 3}]),
])
def test_each_nonreference_change_changes_content_hash(field, value):
    fields = {"items": [{"product_id": 2, "quantity": 1}, {"product_id": 9, "quantity": 3}],
              "requested_for": "private purpose", "pickup_from": None}
    before = proposal(request_fields=fields)
    assert proposal(request_fields={**fields, field: value})["content_sha256"] != before["content_sha256"]


def test_use_intent_hides_note_and_binds_quantity_and_note():
    args = dict(makerspace_id=1, operation_id=OPERATION, original_creator_id=5, product_id=9,
                source_kind="plan", source_id=10, quantity=2, note="private note")
    original = make_use_intent(**args)
    assert "private note" not in str(original)
    assert use_fingerprint_from_snapshot(original) != use_fingerprint_from_snapshot(make_use_intent(**{**args, "note": "other"}))
    assert use_fingerprint_from_snapshot(original) != use_fingerprint_from_snapshot(make_use_intent(**{**args, "quantity": 3}))


def test_sticky_receipt_never_matches_even_identical_digest():
    digest = proposal_fingerprint_from_snapshot(proposal())
    row = SimpleNamespace(fingerprint_version=2, intent_version=2, imported_nonreplayable=True, payload_sha256=digest)
    assert not receipt_matches(row, digest)


@pytest.mark.parametrize("invalid", [True, 0, -1, 9007199254740992])
def test_invalid_reference_is_rejected(invalid):
    with pytest.raises(ValidationError):
        proposal(original_borrower_id=invalid)
