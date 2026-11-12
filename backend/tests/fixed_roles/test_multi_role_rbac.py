"""Object, SQL, and auth payload agree on the valid role union."""
import pytest
from django.db import IntegrityError, connection, transaction

from apps.accounts import rbac
from apps.accounts.serializers import user_payload
from apps.makerspaces.models import MakerspaceMembership, MakerspaceRole, MembershipAdditionalRole
from tests.fixed_roles.helpers import assign_builtin_roles
from tests.return_helpers import make_space, make_user

pytestmark = pytest.mark.django_db


def test_event_and_booking_duties_are_unioned_in_every_surface():
    space = make_space("multi-union")
    actor = make_user("multi-union", access_status="active", account_kind="staff", staff_makerspace=space)
    membership = assign_builtin_roles(actor, space, "event_manager", "booking_manager")
    roles = [MakerspaceRole.objects.get(makerspace=space, slug=slug)
             for slug in ("event_manager", "booking_manager")]
    for action in (rbac.Action.MANAGE_EVENTS, rbac.Action.MANAGE_BOOKINGS):
        assert rbac.can(actor, action, space.pk)
        assert space.pk in rbac.makerspaces_for_action(actor, action)
        assert rbac.scope_by_action(actor, action, type(space).objects.all(), field="id").filter(pk=space.pk).exists()
    assert not rbac.can(actor, rbac.Action.EDIT_INVENTORY, space.pk)
    row = next(row for row in user_payload(actor)["makerspaces"] if row["id"] == space.pk)
    assert row["actions"] == sorted({"manage_events", "manage_bookings"})
    assert row["role_ids"] == [role.pk for role in roles]
    assert row["role_slugs"] == [role.slug for role in roles]
    assert row["role_names"] == [role.name for role in roles]
    assert row["role_id"] == membership.assigned_role_id


@pytest.mark.parametrize("primary,additional,expected", [
    (None, "booking_manager", False),
    ("foreign", "booking_manager", False),
    ("space_manager", "booking_manager", False),
    ("member", "booking_manager", False),
    ("event_manager", "foreign", False),
    ("event_manager", "space_manager", False),
    ("event_manager", "member", False),
])
def test_invalid_additional_roles_never_contribute(primary, additional, expected):
    space, foreign = make_space("multi-invalid"), make_space("multi-foreign")
    actor = make_user("multi-invalid", access_status="active", account_kind="staff", staff_makerspace=space)
    role = lambda slug: MakerspaceRole.objects.get(makerspace=space, slug=slug)
    # One account per person: staff roles live on the staff-track row (a community row holds only Member).
    membership = MakerspaceMembership.staff_tracks.create(
        user=actor, makerspace=space, role="custom", track="staff",
        assigned_role=role("event_manager"),
    )
    foreign_role = MakerspaceRole.objects.get(makerspace=foreign, slug="booking_manager")
    # Deferred constraints allow reads of the corrupt shape inside this savepoint,
    # but PostgreSQL must reject it before it can become durable authority.
    with pytest.raises(IntegrityError), transaction.atomic():
        MakerspaceMembership.staff_tracks.filter(pk=membership.pk).update(
            assigned_role=None if primary is None else foreign_role if primary == "foreign" else role(primary),
        )
        MembershipAdditionalRole.objects.create(
            membership=membership, role=foreign_role if additional == "foreign" else role(additional),
        )
        action = rbac.Action.MANAGE_BOOKINGS
        assert rbac.can(actor, action, space.pk) is expected
        assert (space.pk in rbac.makerspaces_for_action(actor, action)) is expected
        assert rbac.scope_by_action(actor, action, type(space).objects.all(), field="id").filter(pk=space.pk).exists() is expected
        # One account per person: the staff row is this actor's only row here, and the payload reads
        # staff rows through valid_staff_membership_q, so a corrupt one lists no space at all rather
        # than a space with empty roles. Either way no invalid role reaches the console.
        assert not [row for row in user_payload(actor)["makerspaces"] if row["id"] == space.pk]
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
    membership.refresh_from_db()
    assert membership.assigned_role == role("event_manager")
    assert not membership.additional_roles.exists()
