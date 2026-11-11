"""The historical serializer import surface survives the focused split."""

from datetime import timedelta

from django.utils import timezone
import pytest

from apps.bookings import serializers_admin as public
from apps.bookings import serializers_admin_actions as actions
from apps.bookings import serializers_reservation as reservations
from apps.bookings import serializers_space_admin as resources
from apps.bookings import serializers_space_write as writes


@pytest.mark.parametrize("module,names", [
    (resources, ["BookableSpaceAdminSerializer"]),
    (writes, ["BookableSpaceWriteSerializer", "BookableSpaceBookingRulesSerializer"]),
    (reservations, ["BookingAdminSerializer"]),
    (actions, [
        "BookableSpaceListResponseSerializer", "BookingListFilterSerializer",
        "BookingListResponseSerializer", "EmptyActionSerializer",
        "SpaceImageFinalizeRequestSerializer", "SpaceImagePresignRequestSerializer",
        "SpaceImagePresignResponseSerializer", "SpaceImageUploadSerializer",
    ]),
])
def test_every_existing_serializer_is_reexported(module, names):
    for name in names:
        assert getattr(public, name) is getattr(module, name)


def test_resource_write_still_refuses_unknown_fields_and_ignores_server_owned_values():
    serializer = public.BookableSpaceWriteSerializer(data={"name": "Room", "is_active": False})
    assert serializer.is_valid(), serializer.errors
    assert "is_active" not in serializer.validated_data
    serializer = public.BookableSpaceWriteSerializer(data={"name": "Room", "unexpected": 1})
    assert not serializer.is_valid()
    assert "unexpected" in serializer.errors


def test_filter_and_empty_action_validation_survive_the_split():
    now = timezone.now()
    serializer = public.BookingListFilterSerializer(data={
        "starts_at": now.isoformat(), "ends_at": (now - timedelta(hours=1)).isoformat(),
    })
    assert not serializer.is_valid()
    assert "ends_at" in serializer.errors
    serializer = public.EmptyActionSerializer(data={"unexpected": True})
    assert not serializer.is_valid()
