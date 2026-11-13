"""PAY-REVIEW 0.12.0: a campaign's raised total never adds money of another currency.

A gift takes the space's CURRENT default currency, so after a mid-campaign currency change the
public page and the staff list summed rupees with dollars into one figure shown against the
goal. The finance report already split by currency; the campaign card now agrees with it.
"""

from decimal import Decimal

import pytest

from apps.payments.donations.views_public import raised
from apps.payments.models import Donation, DonationCampaign, MakerspacePaymentSettings
from tests.l18_local.helpers import charge_for, gift, settle_offline, setup
from tests.payments.account_helpers import make_payer

pytestmark = pytest.mark.django_db


def test_campaign_total_counts_only_gifts_in_its_own_currency(django_capture_on_commit_callbacks):
    space, manager, donor = setup("prv-don-currency")
    campaign = DonationCampaign.objects.create(makerspace=space, name="Laser", slug="laser", currency="usd",
                                               goal_amount=Decimal(1000))
    first, _ = gift(space, donor, amount="100", campaign=campaign.pk)
    with django_capture_on_commit_callbacks(execute=True):
        settle_offline(manager, charge_for(first))

    merchant = MakerspacePaymentSettings.for_makerspace(space)
    merchant.default_currency = "inr"
    merchant.save()
    second, _ = gift(space, make_payer("prv-don-currency-2", space), amount="5000", campaign=campaign.pk)
    with django_capture_on_commit_callbacks(execute=True):
        settle_offline(manager, charge_for(second), reference="DESK-2")

    second.refresh_from_db()
    assert second.currency == "inr" and second.status == Donation.Status.PAID
    assert raised(campaign) == Decimal(100)
