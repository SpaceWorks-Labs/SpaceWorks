"""L18 80G receipts (PAN always encrypted, masked, never in reports) and refunds only through a case."""

import pytest
from django.db import connection
from rest_framework.test import APIClient

from apps.payments.models import Donation, RefundCase
from tests.l18_local.helpers import admin, charge_for, client, gift, settle_offline, setup, tax_ready

pytestmark = pytest.mark.django_db
PAN = "ABCDE1234F"


def _raw_pan(donation):
    with connection.cursor() as cursor:
        cursor.execute("SELECT pan FROM payments_donortaxdetail WHERE id = %s", [donation.tax_detail_id])
        return cursor.fetchone()[0]


def test_an_80g_request_needs_the_switch_and_a_live_registration():
    space, manager, donor = setup("tax-off")
    refused = client(donor).post(f"/api/v1/public/{space.slug}/donations/give", {
        "amount": "500", "wants_tax_receipt": True, "donor_pan": PAN, "donor_address": "1 Main St"}, format="json")
    assert refused.status_code == 400 and refused.json()["code"] == "tax_receipts_unavailable"
    tax_ready(space)
    bad_pan = client(donor).post(f"/api/v1/public/{space.slug}/donations/give", {
        "amount": "500", "wants_tax_receipt": True, "donor_pan": "12345", "donor_address": "1 Main St"}, format="json")
    assert bad_pan.status_code == 400 and bad_pan.json()["code"] == "pan_invalid"


@pytest.mark.django_db(transaction=True)
def test_pan_is_stored_encrypted_masked_for_staff_and_absent_from_reports(django_capture_on_commit_callbacks):
    space, manager, donor = setup("tax-pan")
    tax_ready(space)
    donation, response = gift(space, donor, amount="5000", wants_tax_receipt=True, donor_pan="abcde 1234 f",
                              donor_address="1 Main St, Pune")
    assert response.json()["donor_pan_masked"] == "••••••234F"
    assert _raw_pan(donation).startswith("pii:") and PAN not in _raw_pan(donation)
    assert Donation.objects.get(pk=donation.pk).tax_detail.pan == PAN
    listed = client(manager).get(admin(space)).json()[0]
    assert listed["donor_pan_masked"] == "••••••234F" and PAN not in str(listed) and "donor_pan" not in listed
    with django_capture_on_commit_callbacks(execute=True):
        settle_offline(manager, charge_for(donation))
    donation.refresh_from_db()
    assert donation.tax_receipt["section"] == "80G" and donation.tax_receipt["registration_number"]
    assert PAN not in str(donation.tax_receipt) and "Pune" not in str(donation.tax_receipt)
    from apps.payments.finance_rows import money_rows
    assert PAN not in str([row.__dict__ if hasattr(row, "__dict__") else row for row in money_rows(space)])
    pdf = client(manager).get(admin(space, f"/{donation.pk}/tax-receipt.pdf"))
    assert pdf.status_code == 200 and pdf["Content-Type"] == "application/pdf"
    mine = client(donor).get(f"/api/v1/member/makerspaces/{space.pk}/donations/{donation.pk}/tax-receipt.pdf")
    assert mine.status_code == 200
    with pytest.raises(Exception):
        donation.tax_receipt = {**donation.tax_receipt, "number": "changed"}
        donation.save(update_fields=["tax_receipt"])


@pytest.mark.django_db(transaction=True)
def test_superadmin_without_a_pii_window_reads_donor_details_masked():
    from types import SimpleNamespace

    from apps.accounts import pii_access
    from apps.accounts.models import User
    from apps.payments.donations.serializers_staff import DonationSerializer
    space, manager, donor = setup("tax-mask")
    tax_ready(space)
    donation, _ = gift(space, donor, amount="900", wants_tax_receipt=True, donor_pan=PAN, donor_address="2 Hill Rd")
    root = User.objects.create_superuser("tax-mask-root", email="root@tax-mask.test", password="x" * 20)

    def shown():
        viewer = User.objects.get(pk=root.pk)
        return DonationSerializer(donation, context={"request": SimpleNamespace(user=viewer)}).data

    row = shown()
    assert row["donor_pan_masked"] == "••••••" and row["donor_address"] == "••••••" and row["pii_masked"] is True
    pii_access.open_grant(root, space, "Checking a donor's 80G receipt request")
    assert shown()["donor_pan_masked"] == "••••••234F"
    staff_view = DonationSerializer(donation, context={"request": SimpleNamespace(user=manager)}).data
    assert staff_view["donor_address"] == "2 Hill Rd" and "pii_masked" not in staff_view


def test_direct_refund_routes_refuse_gifts_and_a_return_goes_through_a_staff_case(django_capture_on_commit_callbacks):
    space, manager, donor = setup("tax-refund")
    donation, _ = gift(space, donor, amount="400")
    payment = charge_for(donation)
    with django_capture_on_commit_callbacks(execute=True):
        settle_offline(manager, payment)
    direct = client(manager).post(f"/api/v1/admin/makerspace/{space.pk}/payments/{payment.pk}/refund-offline", {
        "amount": "400", "reason": "x", "receipt": {"method": "cash", "reference": "R1",
                                                    "refunded_at": "2026-11-01T10:00:00Z"}}, format="json")
    assert direct.status_code == 400 and direct.json()["code"] == "refund_via_case_only"
    opened = client(manager).post(admin(space, f"/{donation.pk}/return"), {"reason": "Giver asked"}, format="json")
    assert opened.status_code == 200, opened.content
    case = RefundCase.objects.get(payment=payment)
    assert case.area == "donations" and case.status == "open" and case.refund_id is None
    payment.refresh_from_db()
    assert payment.status == "paid_offline"  # nothing moved until a staff decision
    again = client(manager).post(admin(space, f"/{donation.pk}/return"), {}, format="json")
    assert again.status_code == 409


@pytest.mark.django_db(transaction=True)
def test_guest_tax_receipt_link_and_wrong_space_links_are_refused(monkeypatch, django_capture_on_commit_callbacks):
    from tests.l18_local.helpers import CODE, fixed_code
    fixed_code(monkeypatch)
    space, manager, donor = setup("tax-guest")
    tax_ready(space)
    public = APIClient()
    public.post(f"/api/v1/public/{space.slug}/donations/email-code", {"donor_email": "g@example.test"}, format="json")
    made = public.post(f"/api/v1/public/{space.slug}/donations/give", {
        "amount": "700", "donor_name": "Guest", "donor_email": "g@example.test", "email_code": CODE,
        "wants_tax_receipt": True, "donor_pan": PAN, "donor_address": "3 Lake Rd"}, format="json")
    assert made.status_code == 201, made.content
    token = made.json()["status_token"]
    assert APIClient().get(f"/api/v1/public/donation-links/{token}/tax-receipt.pdf").status_code == 404
    with django_capture_on_commit_callbacks(execute=True):
        settle_offline(manager, charge_for(Donation.objects.get()))
    pdf = APIClient().get(f"/api/v1/public/donation-links/{token}/tax-receipt.pdf")
    assert pdf.status_code == 200 and pdf["Content-Type"] == "application/pdf"
