"""Shared fixed-catalogue actors; machine reach belongs to the membership."""
from django.db import transaction

from apps.accounts.models import User
from apps.makerspaces.models import Makerspace, MakerspaceMembership, MakerspaceRole
from apps.makerspaces.role_membership_writes import replace_membership_roles
from apps.machines.models_membership_scope import MembershipMachineTypeScope


def _fixture_platform():
    """Only the superadmin may write Space Manager rows (#110), so fixtures act as one."""
    user = User.objects.filter(username="fixture-platform").first()
    return user or User.objects.create_superuser("fixture-platform", "fixture-platform@example.test", None)


def assign_builtin_roles(user, makerspace, *slugs, machine_types=()):
    """One account per person (U-A1): Member goes on the community row, staff roles on
    the person's staff-track row in ``makerspace``."""
    roles = [MakerspaceRole.objects.get(makerspace=makerspace, slug=slug) for slug in slugs]
    track = "community" if set(slugs) == {"member"} else "staff"
    manager = MakerspaceMembership.track_manager(track)
    with transaction.atomic():
        Makerspace.objects.select_for_update().get(pk=makerspace.pk)
        membership, _ = manager.get_or_create(
            user=user, makerspace=makerspace, track=track,
            defaults={"assigned_role": roles[0], "role": roles[0].legacy_role or "custom"},
        )
        membership = manager.select_for_update().get(pk=membership.pk)
        replace_membership_roles(
            membership=membership, roles=roles, actor=_fixture_platform(), reason="test fixture",
        )
        # Machine-type scope belongs to staff rows only (DB guard: a community-track
        # membership cannot hold one), so the Member role carries none.
        if track == "staff":
            MembershipMachineTypeScope.objects.bulk_create([
                MembershipMachineTypeScope(membership=membership, machine_type=kind)
                for kind in machine_types
            ], ignore_conflicts=True)
    return membership


def staff_account(makerspace, username, *slugs, machine_types=(), **fields):
    """A person holding exactly ``slugs`` as staff roles in ``makerspace`` (one account
    per person: the staff-track row, never a separate account)."""
    slugs = slugs or ("space_manager",)
    fields.setdefault("email", f"{username}@example.test")
    fields.setdefault("display_name", username)
    fields.setdefault("access_status", User.AccessStatus.ACTIVE)
    fields.setdefault("role", "space_manager" if "space_manager" in slugs else "requester")
    with transaction.atomic():
        user = User.objects.create_user(username=username, **fields)
        assign_builtin_roles(user, makerspace, *slugs, machine_types=machine_types)
    return user


def roles_for_actions(makerspace, actions):
    """Translate old fixture requests into real built-ins, including their full grants.

    Tests of individually editable grants must instead exercise the fixed role's
    boundaries. This adapter keeps existing helper signatures usable by Part 2.
    """
    from apps.makerspaces.role_catalog import ROLE_CATALOG

    wanted = set(actions)
    if not wanted:
        slugs = ["member"]
    else:
        available = [role for role in ROLE_CATALOG if role.combinable]
        slugs = []
        # Prefer complete duties: inventory before handover, then other duties.
        for role in available:
            if wanted & role.granted_actions:
                slugs.append(role.slug)
                wanted -= role.granted_actions
        if wanted:
            slugs = ["space_manager"]
    return [MakerspaceRole.objects.get(makerspace=makerspace, slug=slug) for slug in slugs]


def membership_for_actions(user, makerspace, actions, *, machine_types=()):
    roles = roles_for_actions(makerspace, actions)
    return assign_builtin_roles(user, makerspace, *(role.slug for role in roles),
                                machine_types=machine_types)
