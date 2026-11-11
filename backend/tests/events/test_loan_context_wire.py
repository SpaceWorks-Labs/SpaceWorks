"""Strict first-slice wire validation; unrun until isolated-test admission."""
import pytest
from apps.events.serializers_loan_context import EventContextPut

GENERATION = "edfa2a9d-3db9-4d8d-8d61-b7a1f6ea94a1"

@pytest.mark.parametrize("bad", [True, 1.0, -1, 9007199254740992])
def test_revision_rejects_non_integer_or_unsafe_number(bad):
    serializer = EventContextPut(data={"expected_generation": GENERATION,
        "expected_revision": bad, "event_id": 7, "participant_registration_id": None})
    assert not serializer.is_valid()


def test_canonical_payload_accepts_zero_revision_and_null_participant():
    serializer = EventContextPut(data={"expected_generation": GENERATION,
        "expected_revision": 0, "event_id": 7, "participant_registration_id": None})
    assert serializer.is_valid(), serializer.errors


def test_unexpected_wire_field_is_not_silently_ignored():
    serializer = EventContextPut(data={"expected_generation": GENERATION,
        "expected_revision": 0, "event_id": 7, "participant_registration_id": None, "admin": True})
    assert not serializer.is_valid()
