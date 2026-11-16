"""O-B1 fixtures: a membership space with units on, a manager, a unit-scoped lead and a few members."""
from datetime import timedelta

from django.utils import timezone

from apps.accounts import rbac
from apps.makerspaces import member_units
from apps.makerspaces.models import MakerspaceMembership
from tests.audit_explorer_helpers import custom_role_member
from tests.makerspaces.l4_helpers import features_on, space_with_manager
from tests.makerspaces.test_membership_j1 import member_role, user


def units_space(slug, *, scoped=True):
    makerspace, boss = space_with_manager(slug)
    makerspace.enabled_modules = sorted(set(makerspace.enabled_modules or []) | {"membership"})
    makerspace.save(update_fields=["enabled_modules"])
    features_on(makerspace, "units", *(("unit_scoped_staff",) if scoped else ()))
    return makerspace, boss


def community_member(makerspace, name):
    person = user(name)
    return MakerspaceMembership.objects.create(
        makerspace=makerspace, user=person, assigned_role=member_role(makerspace), role="custom",
        status="active", activated_at=timezone.now() - timedelta(days=60))


def lead(makerspace, name="lead"):
    """A staff member holding manage_members (and so view_member_units) through a custom role."""
    actor = custom_role_member(makerspace, name, [rbac.Action.MANAGE_MEMBERS])
    return actor, MakerspaceMembership.staff_tracks.get(makerspace=makerspace, user=actor)


def tree(actor, makerspace):
    """District KOCHI under region SOUTH, plus a sibling NORTH."""
    member_units.set_level_names(actor, makerspace, ["Region", "District"])
    south = member_units.create_unit(actor, makerspace, name="South", code="SOUTH")
    kochi = member_units.create_unit(actor, makerspace, name="Kochi", parent_id=south.pk)
    north = member_units.create_unit(actor, makerspace, name="North")
    return south, kochi, north
