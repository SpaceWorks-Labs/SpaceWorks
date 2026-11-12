"""The "spaces and organizations" section of the global profile (decision 304b).

Lists every workspace the person is an ACTIVE member of and every organization they belong to
(explicit rows plus the derived ones of decision 293), with a role title where one is public.
Never listed: revoked memberships, spaces the superadmin hid from the central directory, archived
or paused spaces, and anything of a restricted/suspended account (that account's whole profile is
hidden before this runs). Display-only: nothing here is authority.

Readers other than the owner (decision 336b, SECURITY-REVIEW M13) see a space only when it is
PUBLIC -- its public site is on and it runs the `membership` module, the same test the central
directory uses -- or when they are themselves an active member of it (``shared_ids``); role titles
only when they share at least one space with the person; and organisations only when the
organisation's public profile is on.
"""

from .models import MakerspaceMembership
from .servability import servable_q


def _public_role_title(membership):
    """A title only for the standard roles: custom role names can be internal wording."""
    role = membership.assigned_role
    if membership.role == MakerspaceMembership.Role.CUSTOM:
        return role.name if role is not None and role.is_default else None
    return role.name if role is not None else str(membership.get_role_display())


def listed_memberships(user):
    return (MakerspaceMembership.all_tracks.filter(user=user, status="active")
            .filter(servable_q("makerspace"), makerspace__hidden_from_central_directory=False)
            .select_related("makerspace", "assigned_role").order_by("makerspace__name", "track"))


def listed_space_ids(user):
    return set(listed_memberships(user).values_list("makerspace_id", flat=True))


def _public_space(space):
    from .platform import module_enabled

    return bool(space.public_site_enabled and module_enabled(space, "membership"))


def visible_memberships(user, *, full=False, shared_ids=frozenset()):
    """The listed memberships this reader may see (all of them for the owner)."""
    return [m for m in listed_memberships(user)
            if full or m.makerspace_id in shared_ids or _public_space(m.makerspace)]


def spaces_for(user, *, full=False, shared_ids=frozenset()):
    """One row per space; a staff-track title wins over the community 'Member' one."""
    titles = full or bool(shared_ids)
    rows = {}
    for membership in visible_memberships(user, full=full, shared_ids=shared_ids):
        space = membership.makerspace
        row = rows.setdefault(space.pk, {"slug": space.slug, "name": space.name, "kind": space.kind,
                                         "role_title": None})
        if titles and (membership.track == MakerspaceMembership.Track.STAFF or row["role_title"] is None):
            row["role_title"] = _public_role_title(membership) or row["role_title"]
    return sorted(rows.values(), key=lambda row: row["name"].lower())


def organizations_for(user, *, full=False):
    from apps.organizations.models import Organization, OrganizationMakerspace, OrganizationMembership

    live = Organization.objects.filter(is_active=True, review_status="approved")
    if not full:
        live = live.filter(public_profile_enabled=True)
    found = {}
    explicit = (OrganizationMembership.objects.filter(user=user, status="active", organization__in=live)
                .select_related("organization"))
    for row in explicit:
        found[row.organization_id] = {"slug": row.organization.slug, "name": row.organization.name,
                                      "source": "explicit"}
    owned = OrganizationMakerspace.objects.filter(
        relationship="owner", organization__in=live,
        makerspace_id__in=listed_space_ids(user),
    ).select_related("organization")
    for row in owned:
        found.setdefault(row.organization_id, {"slug": row.organization.slug, "name": row.organization.name,
                                               "source": "derived"})
    return sorted(found.values(), key=lambda row: row["name"].lower())


def spaces_and_organizations(user, *, full=False, shared_ids=frozenset()):
    return {"spaces": spaces_for(user, full=full, shared_ids=shared_ids),
            "organizations": organizations_for(user, full=full)}
