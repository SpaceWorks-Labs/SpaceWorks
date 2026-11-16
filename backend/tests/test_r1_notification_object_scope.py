"""Owner decision #75c (audit NM-71): notification object scope applies to EVERY recipient
kind. People selected by name or as all members get a machine-scoped alert only when they
could see that machine; chat rooms get it only when their own scope admits it."""

import pytest

from apps.accounts.rbac import Action
from apps.integrations.destinations import NotificationScope, resolve_destinations
from apps.integrations.models_destinations import NotificationDestination
from apps.integrations.models_recipients import NotificationRecipient, NotificationRecipientKind
from apps.integrations.staff_notifications import staff_emails_for_feature, staff_user_ids_for_feature
from apps.inventory.models import Category
from apps.machines.models import MachineOperator
from apps.machines.models_membership_scope import MembershipMachineTypeScope
from apps.makerspaces.models import MakerspaceMembership, MakerspaceRole
from tests.test_notification_recipient_scope import make_machine, make_member, make_role, make_space

pytestmark = pytest.mark.django_db


def _members_row(space):
    return NotificationRecipient.objects.create(
        makerspace=space, feature="maintenance", event="logged", kind=NotificationRecipientKind.MEMBERS,
    )


def _member(space, username):
    return make_member(username, space, MakerspaceRole.objects.get(makerspace=space, slug="member"))


def test_members_row_keeps_only_people_who_can_see_the_machine_for_email_and_push():
    space = make_space("os-members")
    printer = make_machine(space, "printer")
    laser = make_machine(space, "laser")
    plain = _member(space, "os-plain")
    operator = _member(space, "os-operator")
    MachineOperator.objects.create(machine=printer, user=operator, access_level=MachineOperator.AccessLevel.OPERATE)
    linked = make_member("os-linked", space, make_role(space, "mm", [Action.MANAGE_MACHINES]))
    MembershipMachineTypeScope.objects.create(
        membership=MakerspaceMembership.all_tracks.get(user=linked, makerspace=space),
        machine_type=printer.machine_type,
    )
    _members_row(space)
    scope = NotificationScope(machine=printer)

    emails = staff_emails_for_feature(space, "maintenance", event="logged", scope=scope)
    pushes = staff_user_ids_for_feature(space, "maintenance", event="logged", scope=scope)

    assert set(emails) == {operator.email, linked.email}
    assert set(pushes) == {operator.pk, linked.pk}
    assert plain.email not in emails
    # The laser is neither operated by nor linked to anyone here but the exempt nobody.
    assert staff_emails_for_feature(space, "maintenance", event="logged", scope=NotificationScope(machine=laser)) == []


def test_a_space_manager_selected_by_name_is_exempt():
    space = make_space("os-named-manager")
    printer = make_machine(space, "printer")
    manager = make_member("os-manager", space, MakerspaceRole.objects.get(makerspace=space, slug="space_manager"))
    NotificationRecipient.objects.create(
        makerspace=space, feature="maintenance", event="logged", kind=NotificationRecipientKind.USER, user=manager,
    )

    assert staff_emails_for_feature(
        space, "maintenance", event="logged", scope=NotificationScope(machine=printer),
    ) == [manager.email]


def test_a_type_only_alert_reaches_an_operator_of_a_machine_of_that_type():
    space = make_space("os-type-only")
    printer = make_machine(space, "printer")
    operator = _member(space, "os-type-operator")
    plain = _member(space, "os-type-plain")
    MachineOperator.objects.create(machine=printer, user=operator, access_level=MachineOperator.AccessLevel.OPERATE)
    _members_row(space)

    emails = staff_emails_for_feature(
        space, "maintenance", event="logged",
        scope=NotificationScope(machine_type=printer.machine_type),
    )

    assert operator.email in emails
    assert plain.email not in emails


def test_alerts_naming_no_machine_are_untouched_for_people():
    space = make_space("os-no-machine")
    category = Category.objects.create(makerspace=space, name="Electronics")
    plain = _member(space, "os-stock-plain")
    _members_row(space)

    assert plain.email in staff_emails_for_feature(
        space, "maintenance", event="logged", scope=NotificationScope(category=category),
    )
    assert plain.email in staff_emails_for_feature(space, "maintenance", event="logged", scope=None)


def test_a_chat_room_receives_a_machine_alert_only_when_its_scope_admits_it():
    space = make_space("os-rooms")
    printer = make_machine(space, "printer")
    laser = make_machine(space, "laser")
    room = NotificationDestination(makerspace=space, channel="slack", label="Laser team")
    room.set_webhook_url("https://hooks.slack.com/services/T000/B000/XXXX")
    room.save()
    room.machine_scopes.create(machine=laser)

    assert resolve_destinations(space, "slack", NotificationScope(machine=laser)) == [room]
    assert resolve_destinations(space, "slack", NotificationScope(machine=printer)) == []
    assert resolve_destinations(space, "slack", None) == []


def test_a_room_scoped_booking_alert_judges_role_rows_by_the_people_rule():
    """#91: for a booking room tied to a machine type, a role recipient is admitted when its
    members can see the room (MANAGE_BOOKINGS), exactly like a named person."""
    space = make_space("os-booking-roles")
    space.enabled_modules = sorted({*space.enabled_modules, "bookings"})
    space.save(update_fields=["enabled_modules"])
    printer = make_machine(space, "printer")
    booking_role = make_role(space, "bookings-team", [Action.MANAGE_BOOKINGS])
    manager = make_member("os-booking-manager", space, booking_role)
    machine_role = make_role(space, "machine-team", [Action.MANAGE_MACHINES])
    unlinked = make_member("os-booking-unlinked", space, machine_role)
    for role in (booking_role, machine_role):
        NotificationRecipient.objects.create(
            makerspace=space, feature="bookings", event="restored", kind=NotificationRecipientKind.ROLE, role=role,
        )

    emails = staff_emails_for_feature(
        space, "bookings", event="restored", scope=NotificationScope(machine_type=printer.machine_type),
    )

    assert manager.email in emails
    assert unlinked.email not in emails
