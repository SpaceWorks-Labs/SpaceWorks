"""Object and SQL twins of the deferred membership constraint, keyed on the TRACK.

Every membership belongs to a person. A community row holds only the Member role; a
staff-track row holds the built-in staff roles (Space Manager alone; every other built-in
staff role combines, including later ones such as Technician). Invalid sets grant
nothing, even before the commit-time trigger runs.
"""

from django.db.models import Exists, F, OuterRef, Q

from apps.makerspaces.role_catalog import COMBINABLE_ROLE_SLUGS

STAFF_ROLES = frozenset({"space_manager", *COMBINABLE_ROLE_SLUGS})


def _person_holds_memberships(user):
    return (user.account_kind == "member" and user.retired_at is None
            and user.merged_into_id is None and user.staff_makerspace_id is None
            and not user.is_superuser and user.role != "superadmin")


def valid_membership_context(membership):
    if membership is None or membership.pk is None or membership.assigned_role_id is None:
        return False
    user, primary = membership.user, membership.assigned_role
    if (not _person_holds_memberships(user) or membership.status not in {"active", "revoked"}
            or primary.makerspace_id != membership.makerspace_id
            or not primary.is_default or not primary.is_protected):
        return False
    links = list(membership.additional_roles.all())
    if membership.track == "community":
        return primary.slug == "member" and not links
    if membership.track != "staff" or primary.slug not in STAFF_ROLES:
        return False
    return all(
        primary.slug in COMBINABLE_ROLE_SLUGS and link.role.slug in COMBINABLE_ROLE_SLUGS
        and link.role_id != primary.pk and link.role.makerspace_id == membership.makerspace_id
        and link.role.is_default and link.role.is_protected
        for link in links
    )


def _person_q():
    return (Q(user__account_kind="member", user__retired_at__isnull=True,
              user__merged_into__isnull=True, user__is_superuser=False,
              user__staff_makerspace__isnull=True)
            & ~Q(user__role="superadmin"))


def valid_staff_membership_q():
    """Correlates against a MakerspaceMembership queryset; invalid sets grant nothing."""
    from apps.makerspaces.models import MembershipAdditionalRole

    invalid_links = MembershipAdditionalRole.objects.filter(membership_id=OuterRef("pk")).exclude(
        membership__assigned_role__slug__in=COMBINABLE_ROLE_SLUGS,
        role__slug__in=COMBINABLE_ROLE_SLUGS, role__is_default=True, role__is_protected=True,
        role__makerspace_id=F("membership__makerspace_id"),
    )
    duplicate_primary = MembershipAdditionalRole.objects.filter(
        membership_id=OuterRef("pk"), role_id=OuterRef("assigned_role_id"),
    )
    return (
        _person_q()
        & Q(track="staff", status__in=["active", "revoked"],
            assigned_role__makerspace_id=F("makerspace_id"), assigned_role__slug__in=STAFF_ROLES,
            assigned_role__is_default=True, assigned_role__is_protected=True)
        & ~Q(Exists(invalid_links)) & ~Q(Exists(duplicate_primary))
    )


def valid_community_membership_q():
    from apps.makerspaces.models import MembershipAdditionalRole

    links = MembershipAdditionalRole.objects.filter(membership_id=OuterRef("pk"))
    return (
        _person_q()
        & Q(track="community", status__in=["active", "revoked"], assigned_role__slug="member",
            assigned_role__makerspace_id=F("makerspace_id"),
            assigned_role__is_default=True, assigned_role__is_protected=True)
        & ~Q(Exists(links))
    )


def valid_membership_q():
    """Either track; callers choose the rows through the manager they query."""
    return valid_community_membership_q() | valid_staff_membership_q()
