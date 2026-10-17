"""Object and SQL twins of the deferred account-membership constraint."""

from django.db.models import Exists, F, OuterRef, Q

from apps.makerspaces.role_catalog import COMBINABLE_ROLE_SLUGS

STAFF_ROLES = frozenset({"space_manager", *COMBINABLE_ROLE_SLUGS})


def valid_membership_context(membership):
    if membership is None or membership.pk is None or membership.assigned_role_id is None:
        return False
    user, primary = membership.user, membership.assigned_role
    if (user.retired_at is not None or user.is_superuser or user.role == "superadmin"
            or membership.status not in {"active", "revoked"}
            or primary.makerspace_id != membership.makerspace_id
            or not primary.is_default or not primary.is_protected):
        return False
    links = list(membership.additional_roles.all())
    if user.account_kind == "member":
        return user.staff_makerspace_id is None and primary.slug == "member" and not links
    if (user.account_kind != "staff" or user.staff_makerspace_id != membership.makerspace_id
            or primary.slug not in STAFF_ROLES
            or list(user.makerspace_memberships.values_list("pk", flat=True)) != [membership.pk]):
        return False
    return all(
        primary.slug in COMBINABLE_ROLE_SLUGS and link.role.slug in COMBINABLE_ROLE_SLUGS
        and link.role_id != primary.pk and link.role.makerspace_id == membership.makerspace_id
        and link.role.is_default and link.role.is_protected
        for link in links
    )


def valid_staff_membership_q():
    """Correlates against a MakerspaceMembership queryset; invalid sets grant nothing."""
    from apps.makerspaces.models import MakerspaceMembership, MembershipAdditionalRole

    other_memberships = MakerspaceMembership.objects.filter(user_id=OuterRef("user_id")).exclude(pk=OuterRef("pk"))
    invalid_links = MembershipAdditionalRole.objects.filter(membership_id=OuterRef("pk")).exclude(
        membership__assigned_role__slug__in=COMBINABLE_ROLE_SLUGS,
        role__slug__in=COMBINABLE_ROLE_SLUGS, role__is_default=True, role__is_protected=True,
        role__makerspace_id=F("membership__makerspace_id"),
    )
    duplicate_primary = MembershipAdditionalRole.objects.filter(
        membership_id=OuterRef("pk"), role_id=OuterRef("assigned_role_id"),
    )
    return (
        Q(user__account_kind="staff", user__retired_at__isnull=True, user__is_superuser=False,
          user__staff_makerspace_id=F("makerspace_id"), status__in=["active", "revoked"],
          assigned_role__makerspace_id=F("makerspace_id"), assigned_role__slug__in=STAFF_ROLES,
          assigned_role__is_default=True, assigned_role__is_protected=True)
        & ~Q(user__role="superadmin") & ~Q(Exists(other_memberships))
        & ~Q(Exists(invalid_links)) & ~Q(Exists(duplicate_primary))
    )


def valid_membership_q():
    from apps.makerspaces.models import MembershipAdditionalRole

    links = MembershipAdditionalRole.objects.filter(membership_id=OuterRef("pk"))
    member = (
        Q(user__account_kind="member", user__retired_at__isnull=True,
          user__is_superuser=False, user__staff_makerspace__isnull=True,
          status__in=["active", "revoked"], assigned_role__slug="member",
          assigned_role__makerspace_id=F("makerspace_id"),
          assigned_role__is_default=True, assigned_role__is_protected=True)
        & ~Q(user__role="superadmin") & ~Q(Exists(links))
    )
    return member | valid_staff_membership_q()
