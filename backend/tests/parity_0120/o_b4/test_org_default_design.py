"""O-B4: one organisation default member-card design across the spaces the organisation owns."""
import pytest

from apps.card_designs import designs, resolution
from apps.card_designs.default_templates import default_document
from apps.card_designs.models import CardDesign
from apps.organizations.models import Organization, OrganizationMakerspace
from tests.l3_local.helpers import card_space, client, manager

pytestmark = pytest.mark.django_db


def _org_with(*spaces, relationship="owner"):
    org = Organization.objects.create(name="Guild", slug="guild-ob4")
    for space in spaces:
        OrganizationMakerspace.objects.create(organization=org, makerspace=space, relationship=relationship)
    return org


def test_resolution_prefers_org_default_over_space_default_in_every_owned_space():
    one, two = card_space("od-one"), card_space("od-two")
    org = _org_with(one, two)
    sm = manager(one)
    row = CardDesign.objects.create(makerspace=one, domain="member_cards", organization=org,
                                    document=default_document("member_cards"))
    designs.publish(sm, row)
    for space in (one, two):
        _document, found = resolution.resolve(space.pk, "member_cards")
        assert found is not None and found.pk == row.pk


def test_an_affiliate_space_does_not_inherit_the_organisation_default():
    owned, affiliate = card_space("od-own"), card_space("od-aff")
    org = _org_with(owned)
    OrganizationMakerspace.objects.create(organization=org, makerspace=affiliate, relationship="affiliate")
    row = CardDesign.objects.create(makerspace=owned, domain="member_cards", organization=org,
                                    document=default_document("member_cards"))
    designs.publish(manager(owned), row)
    assert resolution.resolve(affiliate.pk, "member_cards")[1] is None


def test_creating_the_default_needs_member_card_management_in_every_owned_space():
    one, two = card_space("od-need-one"), card_space("od-need-two")
    org = _org_with(one, two)
    only_one = manager(one)
    denied = client(only_one).post(f"/api/v1/admin/organizations/{org.pk}/card-designs/member-cards", {}, format="json")
    assert denied.status_code == 404  # uniform: no hint the organisation exists
    assert not CardDesign.objects.filter(organization=org).exists()


def test_a_plan_or_title_cannot_ride_with_an_organisation_default():
    from django.db import IntegrityError, transaction
    from apps.makerspaces.models import MembershipTitle
    space = card_space("od-check")
    org = _org_with(space)
    title = MembershipTitle.objects.create(makerspace=space, name="T")
    with pytest.raises(IntegrityError), transaction.atomic():
        CardDesign.objects.create(makerspace=space, domain="member_cards", organization=org, title=title,
                                  document=default_document("member_cards"))
