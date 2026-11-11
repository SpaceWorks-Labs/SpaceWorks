"""L18 donations: the switch, giving as a member or a code-confirmed guest, the charge, receipt and ledger."""

from decimal import Decimal
from unittest.mock import patch

import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.payments.models import Donation, DonationCampaign, Payment, PaymentDocument
from tests.l18_local.helpers import (
    CODE, admin, charge_for, client, fixed_code, gift, give_url, page_url, settle_offline, setup, staff, switch,
)

pytestmark = pytest.mark.django_db


def test_switch_off_hides_every_surface_and_keeps_the_data():
    space, manager, donor = setup("don-off")
    donation, _ = gift(space, donor)
    switch(space, "finance.donations", on=False)
    assert APIClient().get(page_url(space)).status_code == 404
    assert client(donor).post(give_url(space), {"amount": "10"}, format="json").status_code == 404
    assert client(manager).get(admin(space)).status_code == 404
    assert client(donor).get(f"/api/v1/member/makerspaces/{space.pk}/donations").status_code == 404
    assert Donation.objects.filter(pk=donation.pk).exists()  # data kept
    switch(space, "finance.donations")
    assert client(manager).get(admin(space)).json()[0]["id"] == donation.pk


def test_member_gift_raises_one_untaxed_charge_in_the_donations_domain():
    space, manager, donor = setup("don-member", "billing.tax")
    campaign = DonationCampaign.objects.create(makerspace=space, name="New laser", slug="laser", currency="inr",
                                               goal_amount=Decimal("50000"))
    donation, response = gift(space, donor, amount="750", campaign=campaign.pk, note="For the laser")
    payment = charge_for(donation)
    assert payment.member == donor and payment.amount == Decimal("750.00") and payment.tax_snapshot is None
    assert donation.donor == donor and donation.campaign == campaign and donation.status == "pending"
    body = response.json()
    assert body["status_token"] == "" and body["payment_status"] == "pending" and body["campaign"] == "New laser"
    from apps.payments.finance_scope import PAYMENT_DOMAINS
    assert PAYMENT_DOMAINS[payment.subject_type] == "donations"
    assert AuditLog.objects.filter(action="donation.created", target_id=str(donation.pk)).exists()


def test_minimum_campaign_window_and_signed_out_identity_are_enforced():
    space, manager, donor = setup("don-rules")
    closed = DonationCampaign.objects.create(makerspace=space, name="Old", slug="old", currency="inr", is_active=False)
    bad = client(donor).post(give_url(space), {"amount": "0.50"}, format="json")
    assert bad.status_code == 400 and bad.json()["code"] == "amount_below_minimum" and bad.json()["field"] == "amount"
    shut = client(donor).post(give_url(space), {"amount": "10", "campaign": closed.pk}, format="json")
    assert shut.status_code == 400 and shut.json()["code"] == "campaign_closed"
    anonymous = APIClient().post(give_url(space), {"amount": "10"}, format="json")
    assert anonymous.status_code == 400 and anonymous.json()["code"] == "donor_identity_required"
    assert not Donation.objects.exists()


def test_guest_gives_with_the_email_code_and_reads_only_their_own_signed_link(monkeypatch):
    fixed_code(monkeypatch)
    space, manager, donor = setup("don-guest")
    public = APIClient()
    assert public.post(f"/api/v1/public/{space.slug}/donations/email-code",
                       {"donor_email": "guest@example.test"}, format="json").status_code == 202
    wrong = public.post(give_url(space), {"amount": "300", "donor_name": "Grace", "donor_email": "guest@example.test",
                                          "email_code": "000000"}, format="json")
    assert wrong.status_code == 400 and not Donation.objects.exists()
    made = public.post(give_url(space), {"amount": "300", "donor_name": "Grace", "donor_email": "guest@example.test",
                                         "email_code": CODE}, format="json")
    assert made.status_code == 201, made.content
    donation = Donation.objects.get()
    payment = charge_for(donation)
    assert donation.donor is None and payment.member is None and donation.donor_email == "guest@example.test"
    token = made.json()["status_token"]
    shown = APIClient().get(f"/api/v1/public/donation-links/{token}")
    assert shown.status_code == 200 and shown.json()["amount"] == "300.00"
    assert "guest@example.test" not in shown.content.decode() and "Grace" not in shown.content.decode()
    assert APIClient().get(f"/api/v1/public/donation-links/{token}x").status_code == 404
    other = Donation.objects.get().pk
    assert APIClient().get(f"/api/v1/public/donation-links/{other}").status_code == 404


def test_offline_settlement_marks_the_gift_received_with_a_receipt_and_ledger_income(django_capture_on_commit_callbacks):
    space, manager, donor = setup("don-settle")
    donation, _ = gift(space, donor, amount="1200")
    with django_capture_on_commit_callbacks(execute=True):
        settle_offline(manager, charge_for(donation))
    donation.refresh_from_db()
    assert donation.status == "paid" and donation.paid_at is not None
    assert PaymentDocument.objects.filter(payment=charge_for(donation), kind="receipt").exists()
    assert AuditLog.objects.filter(action="donation.paid", target_id=str(donation.pk)).exists()
    from apps.payments.finance_rows import money_rows
    rows = [row for row in money_rows(space) if row.subject_type == "donation"]
    assert rows and rows[0].domain == "donations" and rows[0].amount == Decimal("1200.00")


def test_staff_record_a_desk_gift_in_one_go_and_only_finance_staff_see_gifts():
    space, manager, donor = setup("don-desk")
    response = client(manager).post(admin(space), {
        "amount": "250", "donor_name": "Walk-in giver", "donor_email": "walkin@example.test",
        "settlement": {"method": "cash", "reference": "TILL-7", "received_at": "2026-11-01T10:00:00Z"}},
        format="json")
    assert response.status_code == 201, response.content
    assert response.json()["payment_status"] == "paid_offline" and response.json()["source"] == "desk"
    inventory = staff("don-desk", space, "inventory_manager")
    assert client(inventory).get(admin(space)).status_code == 404
    assert client(donor).get(admin(space)).status_code in (403, 404)


@override_settings(PUBLIC_APP_BASE_URL="http://localhost:5000")
def test_online_rail_returns_a_checkout_url_and_a_provider_failure_keeps_the_gift():
    space, manager, donor = setup("don-online")
    with patch("apps.payments.donations.services.checkout_url", return_value="https://pay.example/x"):
        with patch("apps.payments.availability.online_payments_enabled", return_value=True):
            response = client(donor).post(give_url(space), {"amount": "99"}, format="json")
    assert response.status_code == 201 and response.json()["checkout_url"] == "https://pay.example/x"
    with patch("apps.payments.services.create_checkout_url", side_effect=RuntimeError("provider down")):
        with patch("apps.payments.availability.online_payments_enabled", return_value=True):
            failed = client(donor).post(give_url(space), {"amount": "98"}, format="json")
    assert failed.status_code == 201 and failed.json()["checkout_url"] == ""
    assert Donation.objects.filter(makerspace=space).count() == 2
    assert Payment.objects.filter(makerspace=space, subject_type="donation", status="pending").count() == 2


def test_pending_gift_is_cancelled_by_staff_and_its_charge_cancelled():
    space, manager, donor = setup("don-cancel")
    donation, _ = gift(space, donor)
    response = client(manager).post(admin(space, f"/{donation.pk}/cancel"), {"reason": "duplicate"}, format="json")
    assert response.status_code == 200 and response.json()["status"] == "cancelled"
    assert charge_for(donation).status == "canceled"


def test_a_guest_tells_the_space_they_paid_offline_through_their_own_link(monkeypatch):
    from django.utils import timezone

    from apps.payments.models import PaymentClaim
    fixed_code(monkeypatch)
    space, manager, donor = setup("don-claim", "billing.offline_claims")
    public = APIClient()
    public.post(f"/api/v1/public/{space.slug}/donations/email-code", {"donor_email": "c@example.test"}, format="json")
    made = public.post(give_url(space), {"amount": "150", "donor_name": "Cara", "donor_email": "c@example.test",
                                         "email_code": CODE}, format="json")
    token = made.json()["status_token"]
    claimed = APIClient().post(f"/api/v1/public/donation-links/{token}/claim", {
        "reference": "UTR000111222", "paid_on": timezone.localdate().isoformat()}, format="json")
    assert claimed.status_code == 201, claimed.content
    assert PaymentClaim.objects.get().claimant is None
    switch(space, "billing.offline_claims", on=False)
    assert APIClient().post(f"/api/v1/public/donation-links/{token}/claim", {
        "reference": "UTR000111333", "paid_on": timezone.localdate().isoformat()}, format="json").status_code == 404
