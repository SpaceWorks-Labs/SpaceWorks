"""Account eligibility for explicit organizations; no domain or RBAC dependency."""

from django.db.models import Exists, OuterRef, Q

from apps.accounts.models import User
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.makerspaces.servability import servable_q
from .models import Organization, OrganizationMakerspace, OrganizationMembership


def usable_spaces():
    return Makerspace.objects.filter(servable_q())


def active_accounts(queryset=None):
    return (queryset if queryset is not None else User.objects.all()).filter(
        account_kind=User.AccountKind.MEMBER,
        is_active=True, access_status="active", is_tenant_dump_stub=False,
    )


def eligible_accounts(organization_ids, queryset=None):
    """Batch SQL predicate, independent of action grants and profile publication."""
    organizations = Organization.objects.filter(pk__in=organization_ids, is_active=True)
    direct = OrganizationMembership.objects.filter(
        organization_id__in=organizations.values("pk"), user_id=OuterRef("pk"), status="active",
    )
    owned_spaces = OrganizationMakerspace.objects.filter(
        organization_id__in=organizations.values("pk"), relationship="owner",
        makerspace_id__in=usable_spaces().values("pk"),
    )
    local = MakerspaceMembership.objects.filter(
        user_id=OuterRef("pk"), status="active",
        makerspace_id__in=owned_spaces.values("makerspace_id"),
    )
    return active_accounts(queryset).alias(
        audience_direct=Exists(direct), audience_local=Exists(local),
    ).filter(Q(audience_direct=True) | Q(audience_local=True))


def owned_space_ids(organization_ids):
    # Include unavailable rows in the fence: reactivation must also serialize.
    return set(OrganizationMakerspace.objects.filter(
        organization_id__in=organization_ids, relationship="owner",
    ).values_list("makerspace_id", flat=True))


def lock_membership_sources(organization_ids, user_ids, space_ids):
    """Caller holds sorted space locks. Parents -> accounts -> links -> memberships.

    UPDATE/DELETE on these exact rows must wait, including the Django admin paths.
    NO KEY UPDATE accounts allow concurrent foreign-key inserts, preventing reciprocal
    registrations from deadlocking on otherwise unrelated account identities.
    """
    list(Organization.objects.select_for_update().filter(pk__in=organization_ids).order_by("pk"))
    list(User.objects.select_for_update(no_key=True).filter(pk__in=user_ids).order_by("pk"))
    list(OrganizationMakerspace.objects.select_for_update().filter(
        makerspace_id__in=space_ids,
    ).order_by("pk"))
    list(OrganizationMembership.objects.select_for_update().filter(
        organization_id__in=organization_ids, user_id__in=user_ids,
    ).order_by("pk"))
    list(MakerspaceMembership.objects.select_for_update().filter(
        makerspace_id__in=space_ids, user_id__in=user_ids,
    ).order_by("pk"))
