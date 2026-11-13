import pytest
from django.urls import reverse
from django.db import IntegrityError, connection, transaction
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient

from apps.accounts import rbac
from apps.accounts.models import User
from apps.admin_api.services_user_access import reset_user_password
from apps.integrations.models import EmailNotificationMute
from apps.integrations.staff_notifications import staff_emails_for_feature
from apps.makerspaces.models import Makerspace, MakerspaceMembership, MakerspaceRole
from tests.fixed_roles.helpers import assign_builtin_roles


pytestmark = pytest.mark.django_db


def make_user(username, **kwargs):
    # One account per person (U-A1): staff roles come from the staff-track row the test
    # assigns, so the old account_kind/staff_makerspace fixture hints are dropped.
    kwargs.pop("account_kind", None)
    kwargs.pop("staff_makerspace", None)
    return User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="password",
        access_status=User.AccessStatus.ACTIVE, **kwargs,
    )


def make_makerspace(slug):
    return Makerspace.objects.create(name=slug, slug=slug)


def seeded_role(makerspace, legacy_role):
    return MakerspaceRole.objects.get(
        makerspace=makerspace,
        legacy_role=legacy_role,
    )


def membership(user, makerspace, role, assigned_role):
    # Staff roles live on the STAFF track (U-A1); only the Member role is a community row.
    staff = assigned_role.slug != "member"
    manager = MakerspaceMembership.staff_tracks if staff else MakerspaceMembership.objects
    return manager.create(
        user=user,
        makerspace=makerspace,
        role=role,
        assigned_role=assigned_role,
        track=MakerspaceMembership.Track.STAFF if staff else MakerspaceMembership.Track.COMMUNITY,
    )


def test_space_manager_reset_guard_uses_effective_manage_makerspace_action():
    makerspace = make_makerspace("l2b-reset")
    actor = make_user("l2b-reset-actor", account_kind="staff", staff_makerspace=makerspace)
    membership(
        actor,
        makerspace,
        MakerspaceMembership.Role.SPACE_MANAGER,
        seeded_role(makerspace, MakerspaceMembership.Role.SPACE_MANAGER),
    )
    inventory_peer = make_user("l2b-inventory-peer", account_kind="staff", staff_makerspace=makerspace)
    membership(
        inventory_peer,
        makerspace,
        MakerspaceMembership.Role.INVENTORY_MANAGER,
        seeded_role(makerspace, MakerspaceMembership.Role.INVENTORY_MANAGER),
    )
    # Release 2: still refused (U-B owns the final wording of the staff-reset refusal).
    with pytest.raises(PermissionDenied):
        reset_user_password(actor, inventory_peer.pk)

    # Several combinable roles together still never add up to manage_makerspace.
    combined_peer = make_user("l2b-combined-peer", account_kind="staff", staff_makerspace=makerspace)
    assign_builtin_roles(
        combined_peer, makerspace, "inventory_manager", "machine_manager", "event_manager",
        "booking_manager", "handover",
    )
    with pytest.raises(PermissionDenied):  # Release 2: wording owned by U-B
        reset_user_password(actor, combined_peer.pk)

    default_governance_peer = make_user("l2b-default-governance-peer", account_kind="staff", staff_makerspace=makerspace)
    membership(
        default_governance_peer,
        makerspace,
        MakerspaceMembership.Role.SPACE_MANAGER,
        seeded_role(makerspace, MakerspaceMembership.Role.SPACE_MANAGER),
    )
    with pytest.raises(PermissionDenied):  # Release 2: wording owned by U-B
        reset_user_password(actor, default_governance_peer.pk)


def test_printing_recipients_follow_actions_but_mute_display_roles():
    makerspace = make_makerspace("l2b-printing-recipients")
    machine_manager = make_user("l2b-printing-machine-manager", account_kind="staff", staff_makerspace=makerspace)
    assign_builtin_roles(machine_manager, makerspace, "machine_manager")
    event_manager = make_user("l2b-printing-event-manager", account_kind="staff", staff_makerspace=makerspace)
    assign_builtin_roles(event_manager, makerspace, "event_manager")
    space_manager = make_user("l2b-printing-space-manager", account_kind="staff", staff_makerspace=makerspace)
    membership(
        space_manager,
        makerspace,
        MakerspaceMembership.Role.SPACE_MANAGER,
        seeded_role(makerspace, MakerspaceMembership.Role.SPACE_MANAGER),
    )
    # A temporary null primary must never become a notification authority source.
    print_manager = make_user("l2b-printing-print-manager", account_kind="staff", staff_makerspace=makerspace)
    print_membership = membership(print_manager, makerspace, MakerspaceMembership.Role.PRINT_MANAGER,
                                  seeded_role(makerspace, "machine_manager"))
    inventory_manager = make_user("l2b-printing-inventory-manager", account_kind="staff", staff_makerspace=makerspace)
    membership(
        inventory_manager,
        makerspace,
        MakerspaceMembership.Role.INVENTORY_MANAGER,
        seeded_role(makerspace, MakerspaceMembership.Role.INVENTORY_MANAGER),
    )
    EmailNotificationMute.objects.create(
        makerspace=makerspace,
        target=MakerspaceMembership.Role.SPACE_MANAGER,
        stream="printing",
        event="accepted",
        audience="staff",
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        MakerspaceMembership.staff_tracks.filter(pk=print_membership.pk).update(assigned_role=None)
        emails = staff_emails_for_feature(makerspace, "printing", event="accepted")
        assert machine_manager.email in emails
        assert event_manager.email not in emails
        assert space_manager.email not in emails
        assert print_manager.email not in emails
        assert inventory_manager.email not in emails
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
    print_membership.refresh_from_db()
    assert print_membership.assigned_role == seeded_role(makerspace, "machine_manager")


def test_handout_only_recognises_the_builtin_handover_role():
    makerspace = make_makerspace("l2b-handout-only")
    handover = make_user("l2b-handover", account_kind="staff", staff_makerspace=makerspace)
    assign_builtin_roles(handover, makerspace, "handover")
    broader = make_user("l2b-broader-handover", account_kind="staff", staff_makerspace=makerspace)
    assign_builtin_roles(broader, makerspace, "inventory_manager", "handover")

    assert rbac.is_handout_only(handover, makerspace.id)
    assert not rbac.is_handout_only(broader, makerspace.id)


def test_a_retired_guest_admin_membership_string_now_grants_nothing():
    """The removal must stay removed, and must fail CLOSED when it does not.

    Migration 0053 moved every such membership onto a real role row, so no row should hold
    this string at all. If one somehow does -- a hand-written INSERT, a restored old dump --
    the frozen `_MEMBERSHIP_ROLE_ACTIONS` entry is gone, so it resolves to no actions rather
    than to the six the retired built-in used to carry. This is the one place the retired
    string is still named on purpose: naming it is what pins the fail-closed behaviour.
    """
    makerspace = make_makerspace("l2b-retired-guest")
    stale = make_user("l2b-retired-guest-user", account_kind="staff", staff_makerspace=makerspace)
    row = membership(stale, makerspace, "handover", makerspace.roles.get(slug="handover"))
    with pytest.raises(IntegrityError), transaction.atomic():
        MakerspaceMembership.staff_tracks.filter(pk=row.pk).update(assigned_role=None, role="guest_admin")
        assert rbac.effective_actions(stale, makerspace.id) == set()
        assert not rbac.is_handout_only(stale, makerspace.id)
        assert rbac.can(stale, rbac.Action.ISSUE_REQUEST, makerspace.id) is False
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
    row.refresh_from_db()
    assert row.assigned_role.slug == "handover"


def test_switcher_includes_event_manager_only_membership():
    makerspace = make_makerspace("l2b-events-switcher")
    user = make_user("l2b-events-switcher-user", account_kind="staff", staff_makerspace=makerspace)
    assign_builtin_roles(user, makerspace, "event_manager")
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.get(reverse("admin-makerspaces"))

    assert response.status_code == 200
    assert makerspace.id in {row["id"] for row in response.data}
