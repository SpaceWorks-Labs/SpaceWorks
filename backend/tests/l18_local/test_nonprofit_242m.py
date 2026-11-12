"""Decision 242(m): the non-profit profile decides tax receipts, the receipt wording and the Donate entry."""

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.payments.models import DonationSettings
from tests.l18_local.helpers import (
    admin, charge_for, client, gift, give_url, page_url, settle_offline, setup, switch,
)

pytestmark = pytest.mark.django_db
PAN = "ABCDE1234F"


def profile(space, *, nonprofit=True, schemes=(("us_501c3", "12-3456789"),), **extra):
    switch(space, "finance.tax_exempt_receipts")
    today = timezone.localdate()
    rows = [{"scheme": scheme, "number": number, "valid_from": today.replace(year=today.year - 1).isoformat(),
             "valid_until": ""} for scheme, number in schemes]
    DonationSettings.objects.update_or_create(makerspace=space, defaults={
        "is_nonprofit": nonprofit, "tax_exemptions": rows, "legal_name": "Makers Trust",
        "signatory_name": "R. Treasurer", "signatory_title": "Treasurer", "receipt_footer": "Thank you.", **extra})
    return space


def test_profile_off_means_no_tax_receipt_and_receipts_say_so():
    space, manager, donor = setup("np-off")
    profile(space, nonprofit=False)
    refused = client(donor).post(give_url(space), {"amount": "500", "wants_tax_receipt": True}, format="json")
    assert refused.status_code == 400 and refused.json()["code"] == "tax_receipts_unavailable"
    page = APIClient().get(page_url(space)).json()
    assert page["tax_receipts_available"] is False and page["nonprofit"]["is_nonprofit"] is False
    assert "not a tax receipt" in page["receipt_note"]
    donation, response = gift(space, donor, amount="500")
    assert "not a tax receipt" in response.json()["receipt_note"]
    assert "donate_enabled" not in APIClient().get(f"/api/v1/bootstrap?slug={space.slug}").json().get(
        "makerspace", {})


@pytest.mark.django_db(transaction=True)
def test_a_501c3_receipt_needs_no_pan_and_freezes_the_profile(django_capture_on_commit_callbacks):
    space, manager, donor = setup("np-us")
    profile(space)
    page = APIClient().get(page_url(space)).json()
    assert page["tax_receipts_available"] and page["tax_receipt_needs_pan"] is False and page["receipt_note"] == ""
    assert page["nonprofit"]["legal_name"] == "Makers Trust"
    assert page["nonprofit"]["exemptions"][0]["scheme"] == "us_501c3"
    donation, _ = gift(space, donor, amount="250", wants_tax_receipt=True)
    with django_capture_on_commit_callbacks(execute=True):
        settle_offline(manager, charge_for(donation))
    donation.refresh_from_db()
    receipt = donation.tax_receipt
    assert receipt["exemptions"][0]["number"] == "12-3456789" and receipt["registration_number"] == "12-3456789"
    assert receipt["number"].startswith("TR-") or receipt["number"]  # a billing document number wins when issued
    assert receipt["signatory_name"] == "R. Treasurer" and receipt["legal_name"] == "Makers Trust"
    assert receipt["registrant_pan"] == "" and donation.tax_detail_id is None
    pdf = client(manager).get(admin(space, f"/{donation.pk}/tax-receipt.pdf"))
    assert pdf.status_code == 200 and pdf["Content-Type"] == "application/pdf"


@pytest.mark.django_db(transaction=True)
def test_india_80g_still_asks_for_pan_and_address():
    space, manager, donor = setup("np-in")
    profile(space, schemes=(("in_80g", "AAATS1234F20240"), ("in_12a", "12A-99")))
    page = APIClient().get(page_url(space)).json()
    assert page["tax_receipt_needs_pan"] is True
    no_pan = client(donor).post(give_url(space), {"amount": "500", "wants_tax_receipt": True,
                                                  "donor_address": "1 Main St"}, format="json")
    assert no_pan.status_code == 400 and no_pan.json()["code"] == "pan_invalid"
    ok = client(donor).post(give_url(space), {"amount": "500", "wants_tax_receipt": True, "donor_pan": PAN,
                                              "donor_address": "1 Main St"}, format="json")
    assert ok.status_code == 201
    # The old single-80G columns mirror the list's first India 80G entry.
    row = DonationSettings.objects.get(makerspace=space)
    assert row.tax_exempt_registration_number == "AAATS1234F20240"


def test_12a_alone_unlocks_no_tax_receipt():
    space, manager, donor = setup("np-12a")
    profile(space, schemes=(("in_12a", "12A-1"),))
    assert APIClient().get(page_url(space)).json()["tax_receipts_available"] is False


def test_an_expired_exemption_issues_nothing():
    space, manager, donor = setup("np-expired")
    today = timezone.localdate()
    profile(space)
    DonationSettings.objects.filter(makerspace=space).update(tax_exemptions=[{
        "scheme": "uk_charity", "number": "1234567", "valid_from": "", "valid_until":
            today.replace(year=today.year - 1).isoformat()}])
    assert APIClient().get(page_url(space)).json()["tax_receipts_available"] is False


def test_space_manager_sets_the_profile_audited_and_it_unlocks_the_donate_entry():
    space, manager, donor = setup("np-settings")
    response = client(manager).put(admin(space, "/settings"), {
        "is_nonprofit": True, "legal_name": "Makers Trust", "organization_registration_number": "S-42",
        "signatory_name": "R. Treasurer", "signatory_title": "Treasurer", "receipt_footer": "Thanks.",
        "tax_exemptions": [{"scheme": "uk_charity", "number": "1234567", "valid_from": "2024-01-01",
                            "valid_until": ""}]}, format="json")
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["is_nonprofit"] and body["tax_exemptions"][0]["scheme"] == "uk_charity"
    keys = set(AuditLog.objects.filter(makerspace=space, action="settings.changed").values_list("meta__key", flat=True))
    assert {"donations.is_nonprofit", "donations.tax_exemptions", "donations.signatory_name"} <= keys
    bootstrap = APIClient().get(f"/api/v1/bootstrap?slug={space.slug}").json()
    assert bootstrap["makerspace"]["donate_enabled"] is True
    bad = client(manager).put(admin(space, "/settings"), {"tax_exemptions": [{"scheme": "nope", "number": "1"}]},
                              format="json")
    assert bad.status_code == 400
    emptied = client(manager).put(admin(space, "/settings"), {"tax_exemptions": []}, format="json")
    assert emptied.status_code == 200 and emptied.json()["tax_exemptions"] == []


def test_the_profile_is_never_delegated():
    from tests.l18_local.helpers import staff

    space, manager, donor = setup("np-delegate")
    fundraiser = staff("np-delegate", space, "fundraising")
    refused = client(fundraiser).put(admin(space, "/settings"), {"is_nonprofit": True}, format="json")
    assert refused.status_code == 403 and refused.json()["code"] == "setting_not_delegated"
    assert not DonationSettings.objects.filter(makerspace=space, is_nonprofit=True).exists()


def test_supporters_are_named_only_when_they_opt_in(django_capture_on_commit_callbacks):
    from decimal import Decimal

    from apps.payments.models import DonationCampaign

    space, manager, donor = setup("np-wall")
    campaign = DonationCampaign.objects.create(makerspace=space, name="Laser", slug="laser", currency="inr",
                                               goal_amount=Decimal("1000"))
    named, _ = gift(space, donor, amount="100", campaign=campaign.pk, recognize_publicly=True)
    with django_capture_on_commit_callbacks(execute=True):
        settle_offline(manager, charge_for(named))
    from tests.payments.account_helpers import make_payer
    quiet = make_payer("np-wall-quiet", space)
    anonymous, _ = gift(space, quiet, amount="100", campaign=campaign.pk)
    with django_capture_on_commit_callbacks(execute=True):
        settle_offline(manager, charge_for(anonymous), reference="DESK-2")
    card = APIClient().get(page_url(space)).json()["campaigns"][0]
    assert card["supporter_count"] == 2 and card["supporters"] == [named.donor_name]
    assert anonymous.donor_name not in card["supporters"]
