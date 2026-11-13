"""Shared fixtures for the release-2 L4 membership lifecycle tests (local only)."""
from decimal import Decimal

from apps.makerspaces.models import MakerspaceMembership, MakerspaceRole, MembershipPlan
from tests.return_helpers import make_member, make_space, make_user

L4_KEYS = ("plan_rules", "public_plans", "renewal_desk", "import", "admission_tools", "member_numbers", "records",
           "titles", "consent", "erasure", "history", "register_tools", "insights", "monthly_summary")


def features_on(space, *keys):
    keys = keys or L4_KEYS
    space.refresh_from_db()
    wanted = {f"membership.{key}" for key in keys}
    space.enabled_features = sorted(set(space.enabled_features or []) | wanted)
    modules = set(space.enabled_modules or [])
    if {"register_tools", "insights", "monthly_summary"} & set(keys):
        modules.add("reports")
    space.enabled_modules = sorted(modules)
    space.save(update_fields=["enabled_features", "enabled_modules"])
    return space


def features_off(space, *keys):
    keys = keys or L4_KEYS
    space.refresh_from_db()
    gone = {f"membership.{key}" for key in keys}
    space.enabled_features = [key for key in space.enabled_features or [] if key not in gone]
    space.save(update_fields=["enabled_features"])
    return space


def plan(space, name="Monthly", interval="monthly", amount="10.00", **extra):
    return MembershipPlan.objects.create(makerspace=space, name=name, interval=interval,
                                         amount=Decimal(amount), currency="usd", **extra)


def member(slug, space, **user_fields):
    user = make_user(f"{slug}-member", access_status="active", **user_fields)
    role = MakerspaceRole.objects.get(makerspace=space, slug="member")
    return MakerspaceMembership.objects.create(makerspace=space, user=user, assigned_role=role, role="custom",
                                               status="active")


def space_with_manager(slug):
    space = make_space(slug)
    return space, make_member(f"{slug}-mgr", space)
