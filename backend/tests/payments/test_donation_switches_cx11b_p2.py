"""Finance capabilities are ledger-core: gifts, pledges and sponsors survive an absent rail."""
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.payments.donations.models import Donation, DonationCampaign, DonationPledge, DonationSettings, Sponsor
from apps.payments.donations.tax_receipts import freeze
from apps.payments.models import MakerspacePaymentSettings
from tests.accounts.account_factories import make_staff
from tests.modules.switch_matrix_helpers import MODULE_KEYS, live_space
from tests.modules.switch_matrix_object_helpers import client_for
from tests.payments.switch_helpers_cx11b_p2 import route_cycle

pytestmark = [pytest.mark.django_db, pytest.mark.area_payments_ledger]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["finance.donations", "finance.recurring_donations", "finance.sponsors",
                                 "finance.tax_exempt_receipts"])
def test_seeded_donation_finance_surface_retains_objects_off_and_restores_without_online_payments(native, key):
    space = live_space("p2-donation", set(MODULE_KEYS) - {"payments"})
    actor = make_staff(space, username="p2-fundraiser", access_status="active")
    client = client_for(actor, space, native)
    MakerspacePaymentSettings.objects.get_or_create(makerspace=space)
    campaign = DonationCampaign.objects.create(makerspace=space, name="Retained fund", slug="retained-fund", currency="inr")
    pledge = DonationPledge.objects.create(makerspace=space, donor=actor, campaign=campaign, amount=10,
        currency="inr", starts_on=timezone.localdate(), next_due_on=timezone.localdate(), created_by=actor)
    sponsor = Sponsor.objects.create(makerspace=space, name="Retained sponsor", created_by=actor)
    gift = Donation.objects.create(makerspace=space, donor=actor, donor_name="Retained giver", amount=10,
        currency="inr", created_by=actor, wants_tax_receipt=True, status="paid", paid_at=timezone.now())
    policy = DonationSettings.objects.create(makerspace=space, is_nonprofit=True, tax_exemptions=[
        {"scheme": "us_501c3", "number": "TEST-CHARITY", "valid_from": "", "valid_until": ""}])
    assert freeze(gift)["amount"] == "10"
    objects = {"campaign": campaign, "pledge": pledge, "sponsor": sponsor, "gift": gift, "policy": policy}
    kwargs, method, body = {"makerspace_id": space.pk}, "get", None
    if key == "finance.donations":
        name, method, body, kwargs["pk"] = "admin-donation-campaign", "patch", {"description": "Retained change"}, campaign.pk
    elif key == "finance.recurring_donations":
        name = "admin-donation-pledges"
    elif key == "finance.sponsors":
        name, kwargs["pk"] = "admin-sponsor", sponsor.pk
    else:
        name, kwargs["pk"] = "admin-donation-tax-receipt", gift.pk
    response = route_cycle(space, client, objects, key, reverse(name, kwargs=kwargs), method=method, body=body)
    if key == "finance.recurring_donations":
        assert [row["id"] for row in response.data] == [pledge.pk]
    elif key == "finance.tax_exempt_receipts":
        assert response["Content-Type"] == "application/pdf" and response.content.startswith(b"%PDF")
