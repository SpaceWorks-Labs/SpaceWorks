"""One organisation default member-card design across every space the organisation owns (O-B4, parity C21).

There is ONE member card per member (a member of an organisation's home space holds a single card that is
both the space's and the organisation's membership card); this is only the DEFAULT DESIGN of those cards.
The design row is anchored on the organisation's first owned space (`organization` set, no plan or title);
resolution lets every owned space fall back to it before its own space default.

Editing needs `MANAGE_MEMBER_CARDS` in EVERY owned space: the actor's scope must cover all of them
(`scope_by_action`, count equality), so an organisation default can never be changed by someone who could
not change the card in one of the spaces it reaches. Anyone else gets the uniform 404.
"""
from django.db import transaction
from django.utils.translation import gettext
from rest_framework.exceptions import NotFound, ValidationError

from apps.accounts import rbac
from apps.audit import services as audit

from .models import CardDesign


def owned_space_ids(organization_id):
    from apps.organizations.models import OrganizationMakerspace
    return list(OrganizationMakerspace.objects.filter(organization_id=organization_id, relationship="owner")
                .order_by("makerspace_id").values_list("makerspace_id", flat=True))


def owner_organization_id(makerspace_id):
    from apps.organizations.models import OrganizationMakerspace
    return OrganizationMakerspace.objects.filter(makerspace_id=makerspace_id, relationship="owner").values_list(
        "organization_id", flat=True).first()


def can_manage(actor, organization_id):
    """MANAGE_MEMBER_CARDS in every owned space (and at least one is owned)."""
    from apps.makerspaces.models import Makerspace
    ids = owned_space_ids(organization_id)
    if not ids:
        return False
    reachable = rbac.scope_by_action(actor, rbac.Action.MANAGE_MEMBER_CARDS,
                                     Makerspace.objects.filter(pk__in=ids), field="id").count()
    return reachable == len(ids)


def organization_for(actor, organization_id):
    from apps.organizations.models import Organization
    org = Organization.objects.filter(pk=organization_id).first()
    if org is None or not can_manage(actor, organization_id):
        raise NotFound()
    return org


def existing(organization_id):
    return CardDesign.objects.filter(organization_id=organization_id, domain="member_cards",
                                     event__isnull=True).first()


@transaction.atomic
def create(actor, organization, *, template=None, theme="light"):
    """-> (design, created). Seeds from a shipped template; one default per organisation."""
    from .resolution import get_or_create
    ids = owned_space_ids(organization.pk)
    if not ids:
        raise ValidationError({"detail": gettext("This organisation owns no makerspace.")})
    from apps.makerspaces.models import Makerspace
    anchor = Makerspace.objects.get(pk=ids[0])
    row, created = get_or_create(anchor, "member_cards", actor=actor, template=template, theme=theme,
                                 organization=organization)
    if created:
        audit.record(actor, "card_design.org_default_created", makerspace=anchor, target=row,
                     meta={"design_id": row.pk, "organization_id": organization.pk, "spaces": len(ids)})
    return row, created
