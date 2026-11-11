"""The resource detail and batched list agree with broadcast authorization."""

import pytest

from apps.accounts.models import User
from apps.bookings.booking_authority_page import features_for_page
from apps.bookings.broadcasts import authorize
from apps.bookings.models import BookableSpace
from apps.bookings.models_broadcasts import BookingBroadcast
from apps.bookings.serializers_admin import BookableSpaceAdminSerializer
from apps.makerspaces.models import Makerspace
from tests.fixed_roles.helpers import assign_builtin_roles

pytestmark = pytest.mark.django_db


def test_detail_and_page_match_broadcast_authorization():
    tenant = Makerspace.objects.create(
        name="Broadcast venue", slug="broadcast-venue",
        enabled_modules=["bookings", "notifications", "email"],
        enabled_features=["bookings.broadcasts"],
    )
    actor = User.objects.create_user(username="broadcast-manager", access_status="active")  # one account per person: the role grant makes them staff
    assign_builtin_roles(actor, tenant, "booking_manager")
    resources = [BookableSpace.objects.create(makerspace=tenant, name=f"Room {index}")
                 for index in range(2)]
    detail = BookableSpaceAdminSerializer(resources[0], context={"actor": actor}).data
    page = BookableSpaceAdminSerializer(resources, many=True, context={
        "actor": actor, "booking_features": features_for_page(resources),
    }).data
    assert detail["broadcasts_enabled"] is True
    assert all(row["broadcasts_enabled"] is True for row in page)
    authorize(BookingBroadcast(makerspace=tenant, space=resources[0]), actor)


@pytest.mark.parametrize("missing", ["feature", "email", "notifications", "bookings"])
def test_visible_space_still_requires_broadcast_configuration(missing):
    modules = [key for key in ("bookings", "notifications", "email") if key != missing]
    tenant = Makerspace.objects.create(
        name="Configured venue", slug="configured-venue",
        enabled_modules=modules,
        enabled_features=[] if missing == "feature" else ["bookings.broadcasts"],
    )
    resource = BookableSpace.objects.create(makerspace=tenant, name="Room")
    assert features_for_page([resource])[tenant.pk]["broadcasts_enabled"] is False
    assert BookableSpaceAdminSerializer(resource).data["broadcasts_enabled"] is False


def test_batched_flags_keep_tenant_visibility_separate():
    resources = []
    for broadcasts in (True, False):
        tenant = Makerspace.objects.create(
            name=str(broadcasts), slug=f"broadcast-{broadcasts}",
            enabled_modules=["bookings", "notifications", "email"],
            enabled_features=["bookings.broadcasts", "bookings.clone"] if broadcasts else ["bookings.clone"],
        )
        resources.append(BookableSpace.objects.create(makerspace=tenant, name="Room"))
    flags = features_for_page(resources)
    assert flags[resources[0].makerspace_id]["broadcasts_enabled"] is True
    assert flags[resources[1].makerspace_id]["broadcasts_enabled"] is False
    assert all(flags[row.makerspace_id]["clone_enabled"] for row in resources)
