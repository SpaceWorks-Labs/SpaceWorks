"""Load the membership rows one auth payload may describe, per session (one account per person).

A person holds up to two rows per makerspace: a COMMUNITY row (membership, referrals,
verification) and a STAFF row (staff roles and their actions). Which rows a payload shows
depends on the session that asks, never on the client:

- a browser session sees every row (narrowed to the space of a verified custom origin);
- a native MEMBER grant sees active community rows only -- it never carries staff authority;
- a native STAFF grant sees active community rows plus the staff row of its fixed tenant;
- a claim session sees its one claimed community row and no staff row.
"""

from apps.accounts.rbac_roles import additional_roles_prefetch


def session_rows(user, request):
    """Return ``(community, staff, org_space_ids, include_organizations)``."""
    from apps.accounts import rbac
    from apps.accounts.membership_context import valid_staff_membership_q
    from apps.makerspaces.models import MakerspaceMembership
    from apps.makerspaces.origin_scope import origin_scoped_makerspace_id
    from apps.makerspaces.servability import servable_queryset

    community = MakerspaceMembership.objects.filter(user=user)
    staff = servable_queryset(MakerspaceMembership.staff_tracks.filter(
        valid_staff_membership_q(), user=user, status="active"), relation="makerspace")
    archived_ids = rbac.archived_makerspace_ids()
    if archived_ids:
        community = community.exclude(makerspace_id__in=archived_ids)
        staff = staff.exclude(makerspace_id__in=archived_ids)
    org_space_ids, include_organizations = None, True
    claim_context = getattr(user, "_claim_audit_context", None)
    grant = getattr(request, "device_grant", None) if request is not None else None
    if claim_context is not None:
        community = community.filter(pk=claim_context.membership_id)
        staff = staff.none()
    elif grant is not None:
        # Native payloads stay membership-only: X-Makerspace-Id needs an ACTIVE local row,
        # so advertising organization-only spaces would only produce refusals.
        community = community.filter(status="active")
        include_organizations = False
        if getattr(grant, "authority", None) == "staff":
            staff = staff.filter(makerspace_id=grant.staff_makerspace_id)
        else:
            staff = staff.none()
    elif request is not None:
        scoped = origin_scoped_makerspace_id(request)
        if scoped is not None:
            community = community.filter(makerspace_id=scoped)
            staff = staff.filter(makerspace_id=scoped)
            org_space_ids = {scoped}
    community = list(community.select_related("makerspace", "assigned_role")
                     .prefetch_related(additional_roles_prefetch()))
    staff = list(staff.select_related("makerspace", "assigned_role")
                 .prefetch_related(additional_roles_prefetch()))
    # The reverse relation already identifies the account; reuse it for the role validators.
    for row in community + staff:
        row.user = user
    if claim_context is not None:
        org_space_ids = {row.makerspace_id for row in community}
    return community, staff, org_space_ids, include_organizations


def staff_role_entries(staff_rows):
    """The frozen ``staff_roles`` shape: one entry per makerspace where this session holds
    staff authority, with its roles and the actions those roles grant there."""
    from apps.accounts.rbac_actions import actions_for_membership
    from apps.accounts.rbac_roles import membership_roles

    return [{
        "makerspace": {"id": row.makerspace_id, "slug": row.makerspace.slug, "name": row.makerspace.name},
        "roles": [{"id": role.pk, "slug": role.slug, "name": role.name} for role in membership_roles(row)],
        "actions": sorted(actions_for_membership(row)),
    } for row in staff_rows]


def mfa_grace_ends_at(user):
    """#128 C-1 seam: when this person's staff-MFA grace ends. Null until S-A fills it."""
    return None
