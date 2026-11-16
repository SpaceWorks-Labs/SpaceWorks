import pytest

from apps.hardware_requests.contextual_equipment_serializers import (
    ContextualSelfSerializer, ContextualStaffSerializer,
)

OPERATION = "381091a1-0f99-4d3f-9464-55f40986864e"
ITEMS = [{"product_id": 7, "quantity": 1}]


@pytest.mark.parametrize("event,booking", [
    (None, None),
    (8, None),
    (None, "fb4c7c7a-e585-4417-a290-23b6b9d37b0b"),
    (8, "fb4c7c7a-e585-4417-a290-23b6b9d37b0b"),
])
def test_self_accepts_four_context_shapes(event, booking):
    serializer = ContextualSelfSerializer(data={"operation_id": OPERATION, "items": ITEMS,
        "event_registration_id": event, "booking_token": booking})
    assert serializer.is_valid(), serializer.errors


def test_exactly_one_items_or_kit_and_no_context_free_staff():
    for data in (
        {"operation_id": OPERATION},
        {"operation_id": OPERATION, "items": ITEMS, "kit": {"id": 3, "version": 1}},
        {"operation_id": OPERATION, "items": []},
        {"operation_id": OPERATION, "items": ITEMS},
    ):
        serializer = ContextualStaffSerializer(data=data)
        assert not serializer.is_valid()
    serializer = ContextualStaffSerializer(data={"operation_id": OPERATION,
        "event_registration_id": 8, "kit": {"id": 3, "version": 1}})
    assert serializer.is_valid(), serializer.errors


def test_duplicate_items_and_unsafe_identifiers_are_rejected():
    for items in (ITEMS * 2, [{"product_id": 9007199254740992, "quantity": 1}]):
        serializer = ContextualSelfSerializer(data={"operation_id": OPERATION, "items": items})
        assert not serializer.is_valid()
