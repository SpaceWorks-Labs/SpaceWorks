"""Fixed roles x yuyu resource grants: whole-area managers versus per-resource grants."""
from tests.events.manual_grant_fixture import create_manual_grant
import pytest
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.bookings import booking_authority
from apps.bookings import services_rules
from apps.bookings.models import BookableSpace, BookingSpaceStaffGrant
from apps.events import event_authority
from apps.events.models import Event, EventStaffGrant
from apps.makerspaces.resource_grant_locks import lock_tenant_authority
from apps.operations.report_registry import REPORT_REGISTRY
from tests.events.ticketing_helpers import account, event_space, open_event
from tests.fixed_roles.helpers import assign_builtin_roles

pytestmark = pytest.mark.django_db


def _verified(user):
    user.email_verified_at = timezone.now()
    user.save(update_fields=["email_verified_at"])
    return user


def test_event_manager_held_as_additional_role_reaches_every_event():
    space = event_space("union-events")
    first, second = open_event(space), open_event(space)
    manager = _verified(account("union-event-manager", account_kind="staff", staff_makerspace=space))
    assign_builtin_roles(manager, space, "inventory_manager", "event_manager")
    grantee = _verified(account("union-event-grantee"))
    create_manual_grant(makerspace=space, event=first, user=grantee,
                                   granted_by=manager, permissions=["edit_details"])

    reached = set(event_authority.events_for(manager, "edit_details", Event.objects.all())
                  .values_list("pk", flat=True))
    assert {first.pk, second.pk} <= reached
    assert event_authority.can_manage_grants(manager, second)

    granted = set(event_authority.events_for(grantee, "edit_details", Event.objects.all())
                  .values_list("pk", flat=True))
    assert granted == {first.pk}
    assert not event_authority.can(grantee, second, "edit_details")
    assert not event_authority.can_manage_grants(grantee, first)


def test_booking_manager_held_as_additional_role_reaches_every_space():
    space = event_space("union-bookings")
    space.enabled_modules = sorted(set(space.enabled_modules) | {"bookings"})
    space.enabled_features = sorted(set(space.enabled_features) | {"bookings.staff_grants"})
    space.save(update_fields=["enabled_modules", "enabled_features"])
    room = BookableSpace.objects.create(makerspace=space, name="Room")
    bench = BookableSpace.objects.create(makerspace=space, name="Bench")
    manager = _verified(account("union-booking-manager", account_kind="staff", staff_makerspace=space))
    assign_builtin_roles(manager, space, "handover", "booking_manager")
    grantee = _verified(account("union-booking-grantee"))
    BookingSpaceStaffGrant.objects.create(makerspace=space, space=room, user=grantee,
                                          granted_by=manager, permissions=["edit_details"])

    assert set(booking_authority.spaces_for(manager, "edit_details")
               .values_list("pk", flat=True)) >= {room.pk, bench.pk}
    assert booking_authority.can_manage_grants(manager, bench)
    assert set(booking_authority.spaces_for(grantee, "edit_details")
               .values_list("pk", flat=True)) == {room.pk}
    assert not booking_authority.can(grantee, bench, "edit_details")

    services_rules.update_booking_rules(room, actor=manager, booking_lead_time_minutes=30)
    room.refresh_from_db()
    assert room.booking_lead_time_minutes == 30


def test_resource_grant_lock_covers_additional_roles():
    space = event_space("union-locks")
    event = open_event(space)
    manager = _verified(account("union-lock-manager", account_kind="staff", staff_makerspace=space))
    membership = assign_builtin_roles(manager, space, "machine_manager", "event_manager")
    expected = {membership.assigned_role_id, *membership.additional_roles.values_list("role_id", flat=True)}
    assert len(expected) == 2
    with transaction.atomic():
        assert lock_tenant_authority(manager, event).pk == manager.pk


def test_event_and_booking_subject_reports_are_area_keyed():
    for key in ("event-registrations", "event-feedback", "event-attendance-pdf", "event-attendance"):
        assert REPORT_REGISTRY[key].required_action == "manage_events"
    for key in ("booking-resource-utilization", "booking-resource-utilization-pdf",
                "booking-reservations", "booking-answers", "booking-utilization"):
        assert REPORT_REGISTRY[key].required_action == "manage_bookings"


def test_member_machine_scope_write_requires_recent_reauthentication(settings):
    from apps.machines.models import MachineType
    from tests.return_helpers import authenticated_client, make_space, make_user

    space = make_space("union-reauth")
    admin = make_user("union-reauth-admin", access_status="active", account_kind="staff", staff_makerspace=space)
    assign_builtin_roles(admin, space, "space_manager")
    target = make_user("union-reauth-target", access_status="active", account_kind="staff", staff_makerspace=space)
    membership = assign_builtin_roles(target, space, "machine_manager")
    kind = MachineType.objects.create(makerspace=space, name="Laser", slug="union-laser")
    url = reverse("admin-membership-machine-scope", args=[space.pk, membership.pk])
    from rest_framework.test import APIClient
    client = APIClient()
    client.force_authenticate(admin)  # no recent-authentication proof
    assert client.get(url).status_code == 200
    assert client.put(url, {"machine_type_ids": [kind.pk]}, format="json").status_code == 403
    assert not membership.machine_type_scopes.exists()

    verified = authenticated_client(admin)
    response = verified.put(url, {"machine_type_ids": [kind.pk]}, format="json")
    assert response.status_code == 200, response.data
    assert response.data["machine_type_ids"] == [kind.pk]


def test_space_manager_appoints_any_role_set_except_space_manager():
    from apps.makerspaces.models import MakerspaceRole
    from rest_framework.test import APIClient
    from tests.accounts.reauth_helpers import force_recent_authenticate
    from tests.return_helpers import make_space, make_user

    space = make_space("union-appoint")
    manager = make_user("union-appoint-sm", access_status="active", account_kind="staff", staff_makerspace=space)
    assign_builtin_roles(manager, space, "space_manager")
    client = APIClient()
    force_recent_authenticate(client, manager)
    url = f"/api/v1/admin/makerspaces/{space.pk}/staff-accounts/"
    ids = {role.slug: role.pk for role in MakerspaceRole.objects.filter(makerspace=space)}
    response = client.post(url, {
        "display_name": "Appointee", "username": "union-appointee",
        "roles": ["event_manager", "booking_manager", "handover"],
    }, format="json")
    assert response.status_code == 201, response.data
    assert set(response.data["account"]["roles"]) == {"event_manager", "booking_manager", "handover"}
    refused = client.post(url, {
        "display_name": "Denied manager", "username": "union-appointee-sm",
        "roles": ["space_manager"],
    }, format="json")
    assert refused.status_code == 403
