"""R4: every money/tax switch precedes guest proof and desk identity writes."""

from decimal import Decimal

import pytest
from django.db import connection

from apps.accounts.models import EmailVerificationChallenge
from apps.audit.models import AuditLog
from apps.makerspaces.models import Makerspace
from apps.payments.donations import views_public, views_staff
from apps.payments.donations.gates import tax_key
from apps.payments.donations.models import Donation, DonationPledge, DonorTaxDetail
from apps.payments.models import ManualSettlement, Payment
from tests.l18_local.helpers import admin, setup, staff, switch, tax_ready
from tests.modules.switch_matrix_object_helpers import _no_write, client_for, no_domain_writes
from tests.money_modes.helpers import OFFLINE, set_mode
from tests.payments.fundraising_contention_cx14 import refuse_after_disable
from tests.payments.test_fundraising_public_code_cx14 import code_snapshot, creation_world

pytestmark = pytest.mark.django_db(transaction=True)
CHARGES = ("charges.enabled", "charges.donations")
TAX = "finance.tax_exempt_receipts"
TAX_BODY = {"wants_tax_receipt": True, "donor_pan": "ABCDE1234F", "donor_address": "12 Maker Road"}


def tax_form(space, body):
    tax_ready(space)
    # Tenant key preparation stays outside domain transactions and the SQL fence.
    with tax_key(space, (True, TAX_BODY["donor_pan"], TAX_BODY["donor_address"])):
        pass
    body.update(TAX_BODY)


def assert_restored(space, api, url, body, kind, before, *, desk=False):
    response = api.post(url, body, format="json")
    assert response.status_code == 201, response.content
    model = DonationPledge if kind == "pledge" else Donation
    row = model.objects.get(pk=response.json()["id"])
    assert (row.amount, row.donor_id, row.donor_name, row.wants_tax_receipt) == (
        Decimal("25"), None, "Guest", bool(body.get("wants_tax_receipt")))
    assert (Donation.objects.count(), DonationPledge.objects.count(), Payment.objects.count()) == (
        int(kind != "pledge"), int(kind == "pledge"), int(kind != "pledge"))
    action = "pledge.created" if kind == "pledge" else "donation.created"
    assert AuditLog.objects.filter(makerspace=space, action=action).count() == 1
    if desk:
        assert Makerspace.objects.get(pk=space.pk).anonymous_requester_id is not None
        receipt = ManualSettlement.objects.get(payment__makerspace=space)
        assert (receipt.method, receipt.reference, receipt.amount) == ("cash", "CX14-R4", Decimal("25"))
    else:
        proof = EmailVerificationChallenge.objects.get(user_id=before["principal_link"])
        assert proof.consumed_at is not None
        expected = dict(before[EmailVerificationChallenge._meta.label][0], consumed_at=proof.consumed_at)
        assert EmailVerificationChallenge.objects.values().get(pk=proof.pk) == expected
    if kind != "pledge":
        payment = Payment.objects.get(makerspace=space)
        assert (payment.provider, payment.status, payment.subject_id) == (
            "unclaimed", "paid_offline" if desk else "pending", row.pk)
    assert DonorTaxDetail.objects.filter(makerspace=space).count() == int(bool(body.get("wants_tax_receipt")))
    if body.get("wants_tax_receipt"):
        detail = DonorTaxDetail.objects.get(makerspace=space)
        assert (row.tax_detail_id, detail.pan, detail.address) == (detail.pk, "ABCDE1234F", "12 Maker Road")
    return row


@pytest.mark.parametrize("kind", ["gift", "pledge"])
@pytest.mark.parametrize("key", [*CHARGES, TAX])
@pytest.mark.parametrize("contended", [False, True], ids=["already-off", "disable-race"])
def test_guest_switches_preserve_proof_and_restore_same_request(kind, key, contended, monkeypatch):
    space, api, url, body, effects = creation_world(kind, monkeypatch)
    if key == TAX:
        tax_form(space, body)
    before = code_snapshot(space)
    expected = (400, "tax_receipts_unavailable" if key == TAX else "charges_off")
    if contended:
        refuse_after_disable(space, api, url, body, key, expected, monkeypatch, views_public, "public_space")
    else:
        switch(space, key, on=False)
        with no_domain_writes():
            response = api.post(url, body, format="json")
        assert (response.status_code, response.json()["code"]) == expected
    assert code_snapshot(space) == before
    for effect in effects:
        effect.assert_not_called()
    space.refresh_from_db()
    switch(space, key)
    assert_restored(space, api, url, body, kind, before)
    for effect in (effects[0], effects[1], effects[3]):
        effect.assert_not_called()


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", [*CHARGES, TAX])
@pytest.mark.parametrize("contended", [False, True], ids=["already-off", "disable-race"])
def test_desk_switches_precede_new_anonymous_principal(key, native, contended, monkeypatch):
    from unittest.mock import Mock

    space, _manager, _donor = setup("cx14-r4-desk")
    set_mode(space, "donations", OFFLINE)
    switch(space, "billing.maker_checker", on=False)
    actor = staff("cx14-r4-desk", space, "fundraising")
    api = client_for(actor, space, native)
    assert Makerspace.objects.get(pk=space.pk).anonymous_requester_id is None
    effects = [Mock() for _ in range(6)]
    monkeypatch.setattr("apps.integrations.email.send_email_verification_otp", effects[0])
    monkeypatch.setattr("apps.payments.donations.services.checkout_url", effects[1])
    monkeypatch.setattr("apps.payments.donations.notices._send", effects[2])
    monkeypatch.setattr("apps.payments.notifications.notify_payment", effects[3])
    monkeypatch.setattr("apps.payments.notifications_p2.notify_document", effects[4])
    monkeypatch.setattr("apps.makerspaces.limits.reserve_platform_otp_quota", effects[5])
    body = {"amount": "25", "donor_name": "Guest", "donor_email": "guest@example.test",
            "settlement": {"method": "cash", "reference": "CX14-R4", "received_at": "2026-11-14T10:00:00Z"}}
    if key == TAX:
        tax_form(space, body)
    url, before = admin(space), code_snapshot(space)
    expected = (400, "tax_receipts_unavailable" if key == TAX else "charges_off")
    if contended:
        refuse_after_disable(space, api, url, body, key, expected, monkeypatch, views_staff, "staff_space")
    else:
        switch(space, key, on=False)
        with no_domain_writes():
            response = api.post(url, body, format="json")
        assert (response.status_code, response.json()["code"]) == expected
    assert code_snapshot(space) == before
    for effect in effects:
        effect.assert_not_called()
    space.refresh_from_db()
    switch(space, key)
    assert_restored(space, api, url, body, "gift", before, desk=True)


@pytest.mark.parametrize("kind", ["gift", "pledge"])
def test_creation_service_rechecks_tax_after_identity_transaction(kind, monkeypatch):
    from apps.payments.donations.identity import Donor
    from apps.payments.donations.gates import DonationRefused
    from apps.payments.donations.pledges import create_pledge
    from apps.payments.donations.services import create_gift

    space, _, _, body, effects = creation_world(kind, monkeypatch)
    tax_form(space, body)
    stale = Makerspace.objects.get(pk=space.pk)
    switch(space, TAX, on=False)
    before = code_snapshot(space)
    donor = Donor(account=None, actor=space.anonymous_requester, name="Guest", email="guest@example.test")
    tax = (True, "ABCDE1234F", "12 Maker Road")
    with connection.execute_wrapper(_no_write), pytest.raises(DonationRefused) as refusal:
        if kind == "gift":
            create_gift(stale, donor, amount=Decimal("25"), tax=tax)
        else:
            create_pledge(stale, donor, amount=Decimal("25"), interval="monthly", tax=tax)
    assert (refusal.value.status_code, refusal.value.detail["code"]) == (400, "tax_receipts_unavailable")
    assert code_snapshot(space) == before
    for effect in effects:
        effect.assert_not_called()


def test_recurring_period_keeps_existing_tax_detail_when_tax_collection_is_off(monkeypatch):
    from django.utils import timezone
    from apps.payments.donations.pledges import raise_period

    space, api, url, body, effects = creation_world("pledge", monkeypatch)
    tax_form(space, body)
    before = code_snapshot(space)
    pledge = assert_restored(space, api, url, body, "pledge", before)
    details = list(DonorTaxDetail.objects.order_by("pk").values())
    switch(space, TAX, on=False)
    gift = raise_period(pledge, timezone.localdate())
    assert gift is not None
    assert (gift.pledge_id, gift.tax_detail_id, gift.wants_tax_receipt, gift.amount) == (
        pledge.pk, pledge.tax_detail_id, True, Decimal("25"))
    assert list(DonorTaxDetail.objects.order_by("pk").values()) == details
    assert Payment.objects.filter(makerspace=space, subject_id=gift.pk, subject_type="donation").count() == 1
    assert AuditLog.objects.filter(makerspace=space, action="pledge.period_raised").count() == 1
    assert raise_period(pledge, timezone.localdate()) is None
    assert Donation.objects.filter(pledge=pledge).count() == 1


def test_queued_pledge_notice_follows_recurring_switch_and_restores(monkeypatch):
    from types import SimpleNamespace
    from django.utils import timezone
    from apps.payments.donations.notices import eligible
    from apps.payments.donations.pledges import raise_period

    space, api, url, body, _effects = creation_world("pledge", monkeypatch)
    before = code_snapshot(space)
    pledge = assert_restored(space, api, url, body, "pledge", before)
    gift = raise_period(pledge, timezone.localdate())
    envelope = SimpleNamespace(event="pledge_due", makerspace_id=space.pk, audience="requester",
                               context={"row_id": gift.pk}, recipient_id=None)
    retained = code_snapshot(space)
    assert eligible(envelope) is True
    switch(space, "finance.recurring_donations", on=False)
    with connection.execute_wrapper(_no_write):
        assert eligible(envelope) is False
    assert code_snapshot(space) == retained
    switch(space, "finance.recurring_donations")
    assert eligible(envelope) is True
    assert code_snapshot(space) == retained


@pytest.mark.parametrize("key", ["finance.donations", *CHARGES, TAX])
def test_existing_debt_still_settles_and_keeps_tax_metadata_with_switch_off(key, monkeypatch):
    from tests.l18_local.helpers import client
    from tests.return_helpers import settlement_payload

    space, api, url, body, _effects = creation_world("gift", monkeypatch)
    tax_form(space, body)
    before = code_snapshot(space)
    gift = assert_restored(space, api, url, body, "gift", before)
    details = list(DonorTaxDetail.objects.order_by("pk").values())
    switch(space, key, on=False)
    switch(space, "billing.maker_checker", on=False)
    actor = staff("cx14-core-r4", space, "fundraising")
    payment = Payment.objects.get(makerspace=space)
    response = client(actor).post(
        f"/api/v1/admin/makerspace/{space.pk}/payments/{payment.pk}/mark-offline",
        settlement_payload(reference="CX14-CORE-R4"), format="json")
    assert response.status_code == 200, response.content
    payment.refresh_from_db()
    gift.refresh_from_db()
    assert (payment.status, gift.status, gift.wants_tax_receipt, gift.tax_detail_id) == (
        "paid_offline", "paid", True, details[0]["id"])
    assert list(DonorTaxDetail.objects.order_by("pk").values()) == details
    assert ManualSettlement.objects.get(payment=payment).reference == "CX14-CORE-R4"
    assert AuditLog.objects.filter(makerspace=space, action="donation.paid").count() == 1
