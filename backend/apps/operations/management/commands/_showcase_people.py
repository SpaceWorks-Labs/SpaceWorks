"""The showcase makerspace itself, its staff, its members and one restricted account.

The space is created through the staff create serializer (owner organization and
the `makerspace.created` audit included), modules through `apply_profile`
and every capability through `setup_settings.save_space`, the audited settings path.
Staff are people granted roles through `grant_staff_role`; members join through invite
+ approval, the same membership services the console uses, which also raises their dues.
"""
from types import SimpleNamespace

from django.core.management.base import CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.staff_identity import context_label
from apps.accounts.models import User
from apps.accounts.principal_guards import refuse_anonymous_requester_access_mutation
from apps.admin_api.permissions import require_user_access_mutation
from apps.admin_api.serializers_makerspaces import MakerspaceSerializer
from apps.audit import services as audit
from apps.machines.models import MachineType
from apps.makerspaces.capabilities import FEATURES
from apps.makerspaces.capability_validation import prune_features
from apps.makerspaces.membership_services import approve_request, invite_membership
from apps.makerspaces.module_install import apply_profile
from apps.makerspaces.module_profiles import EVERYTHING
from apps.makerspaces.models import MakerspaceMembership
from apps.makerspaces.setup_settings import save_space
from apps.makerspaces.staff_role_grants import grant_staff_role
from apps.organizations.models import Organization

from . import _showcase_data as data

# Requiring TOTP enrolment would stop every showcase staff login at the MFA wall.
# The two-person check (L5) would park every seeded desk receipt waiting for a second
# person; the showcase demonstrates settled dues, so it stays off like staff MFA.
FEATURES_LEFT_OFF = frozenset({"security.staff_mfa_required", "billing.maker_checker"})


def member_account(username, display_name, password, kind="member", **flags):
    user = User.objects.filter(username=username).first()
    if user is None:
        user = User.objects.create_user(
            username, email=f"{username.replace('_', '.')}@example.org", password=password,
            account_kind=kind, display_name=display_name, **flags,
        )
    if context_label(user) != kind or user.retired_at is not None:
        raise CommandError(f"Existing account {username!r} is not a reusable {kind} account.")
    user.display_name, user.phone = display_name, "+44 7700 900123"
    user.must_change_password = False
    user.set_password(password)
    # No service verifies an email without a delivered OTP; the tests set it the same way.
    user.email_verified_at = user.email_verified_at or timezone.now()
    user.save()
    return user


def create_space(root):
    organization = Organization.objects.filter(name=data.ORGANIZATION).first()
    owner = ({"organization_id": organization.pk} if organization
             else {"organization_name": data.ORGANIZATION})
    serializer = MakerspaceSerializer(data={
        "name": data.NAME, "slug": data.SLUG, "location": data.LOCATION,
        "public_inventory_enabled": True, **owner,
    }, context={"request": SimpleNamespace(user=root)})
    serializer.is_valid(raise_exception=True)
    space = serializer.save(created_by=root)
    audit.record(root, "makerspace.created", makerspace=space, target=space)
    apply_profile(space, EVERYTHING, actor=root)
    space.refresh_from_db()
    # Every feature the installed module set can carry; a module this deployment does
    # not ship would otherwise make the whole capability write refuse.
    features, _unsupported = prune_features(
        [key for key in FEATURES if key not in FEATURES_LEFT_OFF], space.enabled_modules)
    space = save_space(root, space, {
        "enabled_features": features,
        "public_site_enabled": True,
        "public_stats_enabled": True,
        "public_display_name": data.NAME,
        "membership_dues_amount": "25.00",
    })
    # L26 (#170): every stats section, a headline row and the lobby TV board.
    from apps.makerspaces.public_stats_settings import save_config
    save_config(root, space, {
        "sections": ["events", "machines", "printing", "lending", "community"],
        "headline": ["community.active_members", "events.attendees", "printing.hours", "lending.loans"],
        "tv_mode_enabled": True,
    })
    return space


def create_staff(space, root, password):
    builtin_types = list(MachineType.objects.filter(makerspace__isnull=True, is_builtin=True)
                         .values_list("pk", flat=True))
    staff = {}
    for username, name, role_slug in data.STAFF:
        # One account per person: a staff member is a person granted roles (#63).
        user = member_account(username, name, password)
        if not MakerspaceMembership.staff_tracks.filter(makerspace=space, user=user).exists():
            grant_staff_role(
                makerspace=space, user=user, actor=root, roles=[space.roles.get(slug=role_slug)],
                machine_type_ids=builtin_types if role_slug == "machine_manager" else [],
            )
        staff[role_slug] = user
    # Settings authority (#101): the demo Machine Manager runs machine settings themselves;
    # the Inventory Manager shows the read-only state with only rental timing editable.
    from apps.makerspaces.settings_authority_writes import set_grants
    set_grants(root, space, "machines", [staff["machine_manager"].pk])
    return SimpleNamespace(manager=staff["space_manager"], inventory=staff["inventory_manager"],
                           machines=staff["machine_manager"], desk=staff["handover"])


def create_members(space, root, manager, plan, password):
    role = space.roles.get(slug="member")
    members = {}
    for username, name in (*data.MEMBERS, data.RESTRICTED_MEMBER):
        user = restore(root, member_account(username, name, password))
        invite = invite_membership(manager, space, user.email, role)
        approve_request(manager, invite, role, plan=plan)
        members[username] = user
    return members


def restrict(root, user, reason):
    """Mirror of the superadmin restrict endpoint: its guards, write and audit entry."""
    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=user.pk)
        require_user_access_mutation(root, user)
        refuse_anonymous_requester_access_mutation(user)
        user.access_status = User.AccessStatus.RESTRICTED
        user.restriction_reason = reason
        user.save(update_fields=["access_status", "restriction_reason"])
        audit.record(root, "user.access_restricted", target=user,
                     meta={"status": user.access_status, "reason": reason})
    return user


def restore(root, user):
    """Mirror of the superadmin restore endpoint, for a member left restricted by a
    previous showcase run (members are global accounts and survive the purge)."""
    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=user.pk)
        if user.access_status == User.AccessStatus.ACTIVE:
            return user
        require_user_access_mutation(root, user)
        refuse_anonymous_requester_access_mutation(user)
        user.access_status = User.AccessStatus.ACTIVE
        user.restriction_reason = ""
        user.save(update_fields=["access_status", "restriction_reason"])
        audit.record(root, "user.access_restored", target=user)
    return user
