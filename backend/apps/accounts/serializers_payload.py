"""The auth payload (`/auth/me`, sign-in and refresh responses), frozen for release 2.

One account per person (#62/#63): the payload says WHO the account is (``kind`` =
``person`` | ``platform``) and what staff authority THIS session may exercise
(``staff_roles``). ``makerspaces`` keeps one entry per space with the session's effective
actions there, merging the person's community row, staff row and organization grants.
The shape is documented in ``schemas_auth.AuthUserPayload``.
"""

from apps.accounts.models import User
from apps.accounts.org_payload import (
    membership_makerspace_entry,
    organization_makerspace_entries,
)
from apps.accounts.payload_tracks import mfa_enrolment_due, mfa_grace_ends_at, session_rows, staff_role_entries
from apps.accounts.staff_identity import has_elevated_authority, has_staff_role, is_person, is_platform
from apps.accounts.surface_policy import token_kind
from config.locale_registry import locale_list_payload


VERIFICATION_ONLY_SURFACE = "verification_only"
DEVICE_REFRESH_CLAIMS = ("device_grant_id", "device_family_id")
# ``person`` or ``platform``; an inert shell has no session and no payload kind.
payload_kind = token_kind


def handle_state(user, person):
    """Decision 308: the account's handle, and the blocking-step flag + suggestion when it has none."""
    if not person or getattr(user, "account_kind", "") != "member" or user.is_walk_in:
        return {"handle": None, "handle_required": False, "handle_suggestion": None}
    from apps.makerspaces.public_profile_handles import suggestion_for
    from apps.makerspaces.models_profiles import PublicHandle

    handle = PublicHandle.objects.filter(user_id=user.pk).values_list("handle", flat=True).first()
    return {"handle": handle, "handle_required": handle is None,
            "handle_suggestion": None if handle else suggestion_for(user)}


def user_payload(user, request=None, *, session_authority=None):
    from apps.accounts import rbac
    from apps.machines import role_scope

    community, staff, org_space_ids, include_organizations = session_rows(user, request)
    claim_context = getattr(user, "_claim_audit_context", None)
    is_superadmin = user.is_superuser or user.role == User.Role.SUPERADMIN
    organization_entries = (
        organization_makerspace_entries(user, makerspace_ids=org_space_ids)
        if include_organizations else {}
    )
    organization_actions = {space_id: set(entry["actions"])
                            for space_id, entry in organization_entries.items()}
    # Batched so /auth/me and /auth/login stay O(1) queries rather than one per space.
    machine_scopes = role_scope.manage_scopes_for_memberships(staff)
    staff_by_space = {row.makerspace_id: row for row in staff}
    community_by_space = {row.makerspace_id: row for row in community}

    def _actions(row):
        if is_superadmin:
            return sorted(rbac.ROLE_GRANTABLE_ACTIONS)
        return sorted(rbac.actions_for_membership(row) | organization_actions.get(row.makerspace_id, set()))

    def _is_machine_only(row, actions):
        """The console's batched copy of `role_scope.is_machine_only` (kept in step: it
        decides whether the Notifications tab renders, and the inbox refuses this actor)."""
        if is_superadmin or rbac.Action.MANAGE_MACHINES not in actions:
            return False
        if machine_scopes.get(row.pk, role_scope.NOTHING) is role_scope.EXEMPT:
            return False
        from apps.accounts.rbac_roles import stored_actions_for_membership
        # STORED, not effective: MANAGE_MACHINES always implies MANAGE_PRINTING when expanded.
        if rbac.Action.MANAGE_PRINTING in stored_actions_for_membership(row):
            return False
        return not (rbac.Action.VIEW_INVENTORY in actions or rbac.Action.MANAGE_MAKERSPACE in actions)

    def _entry(space_id):
        from apps.accounts.rbac_roles import membership_roles
        community_row, staff_row = community_by_space.get(space_id), staff_by_space.get(space_id)
        # Role identity comes from the staff row when there is one (it holds the roles).
        primary = staff_row or community_row
        actions = _actions(primary)
        entry = membership_makerspace_entry(
            primary, actions=actions,
            can_configure_machine_types=is_superadmin or any(
                role.slug == "space_manager" for role in membership_roles(primary)),
            is_machine_only=_is_machine_only(primary, set(actions)),
        )
        if community_row is not None and staff_row is not None:
            entry.update(can_refer=community_row.can_refer, can_verify=community_row.can_verify,
                         verified_at=community_row.verified_at)
        entry["tracks"] = [track for track, row in (("community", community_row), ("staff", staff_row))
                           if row is not None]
        return entry

    space_ids = list(community_by_space) + [space for space in staff_by_space if space not in community_by_space]
    entries = [_entry(space_id) for space_id in space_ids]
    org_only = [entry for space_id, entry in organization_entries.items() if space_id not in set(space_ids)]

    from apps.makerspaces.resource_grant_sources import payload_entries
    resource_grants = (
        payload_entries(user, makerspace_ids=org_space_ids)
        if include_organizations and claim_context is None else {}
    )
    if not include_organizations and claim_context is None:
        # #173: native sessions list event roles (an event grant: its own event only). Listing
        # grants no authority; the route gate admits a programme route only on an event grant.
        from apps.accounts.native_event_grants import native_event_grant_entries
        resource_grants = native_event_grant_entries(user, getattr(request, "device_grant", None))
    person = is_person(user)
    return {
        **resource_grants,
        "session_authority": _session_authority(user, request, session_authority),
        "id": user.id,
        "username": user.username,
        **handle_state(user, person),
        "email": user.email,
        "display_name": user.display_name,
        "phone": user.phone,
        "email_verified": user.email_verified_at is not None,
        "role": user.role,
        "is_superuser": user.is_superuser,
        "must_change_password": user.must_change_password,
        "kind": payload_kind(user),
        "is_platform": is_platform(user),
        # Decision 361: a restricted or suspended person signs in to pay what they owe.
        "account_status": _account_status(user),
        "has_staff_role": person and has_staff_role(user),
        "has_elevated_authority": person and has_elevated_authority(user),
        # 0.12.0 audit row 9: the console shows its cross-venue Organizations group only to a
        # person who belongs to an organization. Native and claim sessions carry no org authority.
        "has_organizations": person and include_organizations and claim_context is None and _has_organizations(user),
        "staff_roles": staff_role_entries(staff),
        "makerspaces": entries + org_only,
        # A platform account has no memberships; the console reads its per-space actions here.
        "superadmin_actions": sorted(rbac.ROLE_GRANTABLE_ACTIONS) if is_superadmin else [],
        "mfa_grace_ends_at": mfa_grace_ends_at(user),
        "merge_suggested": person and claim_context is None and _merge_suggested(user),
        "mfa_enrolment_due": mfa_enrolment_due(user),
        # Phase 8 i18n: the stored preference (null follows the makerspace default), what this
        # request resolved to, and every locale the switcher may offer.
        "preferred_locale": user.preferred_locale,
        "effective_locale": _effective_locale(user, request),
        "supported_locales": locale_list_payload(),
    }


def _effective_locale(user, request):
    from config.locale_resolution import ambient_from_request, explicit_from_request, resolve

    if request is None:
        return resolve(user=user)[0]
    return resolve(explicit=explicit_from_request(request), user=user, ambient=ambient_from_request(request))[0]


def _has_organizations(user):
    """One indexed EXISTS: an ACTIVE membership of an active organization (what the
    Organizations list itself shows, `organizations.access.visible_organizations`)."""
    from apps.organizations.access import visible_organizations
    return visible_organizations(user).exists()


def _merge_suggested(user):
    from apps.accounts.account_merge_eligibility import merge_suggested
    return merge_suggested(user)


def _session_authority(user, request, issued_surface):
    """``member``, ``native_staff``, ``platform`` or ``verification_only``."""
    if user.self_registered_at is not None and user.email_verified_at is None:
        return VERIFICATION_ONLY_SURFACE
    grant = getattr(request, "device_grant", None)
    if grant is not None:
        from apps.accounts.native_event_grants import session_authority_for
        return session_authority_for(grant)
    surface = issued_surface or getattr(request, "session_authority", None)
    if surface is None:
        token = getattr(request, "auth", None)
        surface = token.get("surface", "member") if token else "member"
    return "member" if surface == VERIFICATION_ONLY_SURFACE else surface


def _account_status(user):
    from apps.accounts.restricted_admission import account_status
    return account_status(user)
