"""Historical guest retirement uses pre-constraint models; current Handover is built-in."""
import pytest

from apps.makerspaces.models import Makerspace, MakerspaceMembership, MakerspaceRole
from tests.fixed_roles.migration_helpers import old_database


@pytest.mark.django_db(transaction=True)
def test_a_new_makerspace_gets_no_guest_admin_role():
    """The removed Guest Admin spelling must not be reseeded."""
    makerspace = Makerspace.objects.create(name="No guest", slug="no-guest")

    assert not MakerspaceRole.objects.filter(
        makerspace=makerspace, legacy_role="guest_admin"
    ).exists()
    assert not MakerspaceRole.objects.filter(makerspace=makerspace, slug="guest_admin").exists()


@pytest.mark.django_db(transaction=True)
def test_the_migration_converts_a_seeded_guest_admin_without_touching_its_actions(old_database):
    """Converting in place is the point: memberships PROTECT the row, so it cannot be
    dropped and recreated without revoking everyone who holds it."""
    Makerspace = old_database.get_model("makerspaces", "Makerspace")
    MakerspaceRole = old_database.get_model("makerspaces", "MakerspaceRole")
    MakerspaceMembership = old_database.get_model("makerspaces", "MakerspaceMembership")
    def make_user(username):
        return old_database.get_model("accounts", "User").objects.create(username=username, password="!")

    from importlib import import_module

    makerspace = Makerspace.objects.create(name="Legacy guest", slug="legacy-guest")
    legacy = MakerspaceRole.objects.create(
        makerspace=makerspace,
        name="Guest Admin",
        slug="guest_admin",
        legacy_role="guest_admin",
        granted_actions=["assign_box", "issue_request", "return_request", "view_inventory"],
        is_default=True,
        is_protected=True,
    )
    holder = MakerspaceMembership.objects.create(
        makerspace=makerspace, user=make_user("legacy-guest-holder"), assigned_role=legacy,
    )

    module = import_module("apps.makerspaces.migrations.0052_retire_builtin_guest_admin_role")
    module.forwards(old_database, None)

    legacy.refresh_from_db()
    assert legacy.legacy_role is None
    assert legacy.is_default is False
    assert legacy.is_protected is False
    # Untouched: identity, authority and the assignment.
    assert legacy.name == "Guest Admin"
    assert legacy.granted_actions == [
        "assign_box", "issue_request", "return_request", "view_inventory"
    ]
    holder.refresh_from_db()
    assert holder.assigned_role_id == legacy.pk


@pytest.mark.django_db(transaction=True)
def test_0053_moves_a_null_fk_guest_membership_onto_a_role_with_the_same_authority(old_database):
    """The null-FK membership is the one that was living off the frozen fallback, so it is
    the one that loses authority if the conversion gets the action set wrong."""
    Makerspace = old_database.get_model("makerspaces", "Makerspace")
    MakerspaceRole = old_database.get_model("makerspaces", "MakerspaceRole")
    MakerspaceMembership = old_database.get_model("makerspaces", "MakerspaceMembership")
    def make_user(username):
        return old_database.get_model("accounts", "User").objects.create(username=username, password="!")

    from importlib import import_module

    makerspace = Makerspace.objects.create(name="Null fk guest", slug="null-fk-guest")
    stale = MakerspaceMembership.objects.create(
        makerspace=makerspace,
        user=make_user("null-fk-guest-holder"),
        role="guest_admin",
        assigned_role=None,
    )

    module = import_module("apps.makerspaces.migrations.0053_convert_guest_admin_memberships")
    module.forwards(old_database, None)

    stale.refresh_from_db()
    assert stale.role == "custom"
    assert stale.assigned_role is not None
    # Exactly the six the retired built-in granted -- widening here would be a silent grant.
    assert stale.assigned_role.granted_actions == [
        "assign_box", "issue_direct_loan", "issue_request",
        "return_request", "upload_evidence", "view_inventory",
    ]
    assert stale.assigned_role.legacy_role is None
    assert stale.assigned_role.is_default is False


@pytest.mark.django_db(transaction=True)
def test_0053_reuses_an_untouched_handover_role_rather_than_making_a_second_one(old_database):
    Makerspace = old_database.get_model("makerspaces", "Makerspace")
    MakerspaceRole = old_database.get_model("makerspaces", "MakerspaceRole")
    MakerspaceMembership = old_database.get_model("makerspaces", "MakerspaceMembership")
    def make_user(username):
        return old_database.get_model("accounts", "User").objects.create(username=username, password="!")

    from importlib import import_module

    makerspace = Makerspace.objects.create(name="Reuse guest", slug="reuse-guest")
    converted = MakerspaceRole.objects.create(
        makerspace=makerspace,
        name="Guest Admin",
        slug="guest_admin",
        legacy_role=None,
        granted_actions=[
            "assign_box", "issue_direct_loan", "issue_request",
            "return_request", "upload_evidence", "view_inventory",
        ],
        is_default=False,
        is_protected=False,
    )
    stale = MakerspaceMembership.objects.create(
        makerspace=makerspace,
        user=make_user("reuse-guest-holder"),
        role="guest_admin",
        assigned_role=None,
    )

    module = import_module("apps.makerspaces.migrations.0053_convert_guest_admin_memberships")
    module.forwards(old_database, None)

    stale.refresh_from_db()
    assert stale.assigned_role_id == converted.pk
    assert not MakerspaceRole.objects.filter(
        makerspace=makerspace, slug__startswith="front-desk"
    ).exists()


@pytest.mark.django_db(transaction=True)
def test_0053_does_not_widen_a_membership_whose_handover_role_was_reshaped(old_database):
    """An operator who widened the converted role after 0052 must not have that widening
    handed to a membership that was still resolving through the frozen six."""
    Makerspace = old_database.get_model("makerspaces", "Makerspace")
    MakerspaceRole = old_database.get_model("makerspaces", "MakerspaceRole")
    MakerspaceMembership = old_database.get_model("makerspaces", "MakerspaceMembership")
    def make_user(username):
        return old_database.get_model("accounts", "User").objects.create(username=username, password="!")

    from importlib import import_module

    makerspace = Makerspace.objects.create(name="Widened guest", slug="widened-guest")
    widened = MakerspaceRole.objects.create(
        makerspace=makerspace,
        name="Guest Admin",
        slug="guest_admin",
        legacy_role=None,
        granted_actions=["edit_inventory", "issue_request", "view_inventory"],
        is_default=False,
        is_protected=False,
    )
    stale = MakerspaceMembership.objects.create(
        makerspace=makerspace,
        user=make_user("widened-guest-holder"),
        role="guest_admin",
        assigned_role=None,
    )

    module = import_module("apps.makerspaces.migrations.0053_convert_guest_admin_memberships")
    module.forwards(old_database, None)

    stale.refresh_from_db()
    assert stale.assigned_role_id != widened.pk
    assert stale.assigned_role.slug == "front-desk"
    assert "edit_inventory" not in stale.assigned_role.granted_actions
