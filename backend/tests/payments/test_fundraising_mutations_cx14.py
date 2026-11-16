"""R1: real logo-delete and claim decisions refuse before any domain write."""

from decimal import Decimal
from unittest.mock import Mock

import pytest
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.makerspaces.local_time import local_now
from apps.payments.donations.identity import Donor
from apps.payments.donations.models import Donation, DonationCampaign, Sponsor, SponsorshipCharge
from apps.payments.donations.services import create_gift
from apps.payments.models import ManualSettlement, Payment, PaymentClaim
from apps.payments.offline_claims import submit_claim
from tests.l18_local.helpers import admin, setup, staff, switch
from tests.modules.switch_matrix_object_helpers import client_for, no_domain_writes
from tests.money_modes.helpers import OFFLINE, set_mode
from tests.return_helpers import settlement_payload

pytestmark = pytest.mark.django_db
DOMAIN_MODELS = (Donation, DonationCampaign, Sponsor, SponsorshipCharge, Payment, PaymentClaim, ManualSettlement)


def snapshot(space):
    return {model._meta.label: list(model.objects.filter(**{
                "payment__makerspace" if model is ManualSettlement else "makerspace": space,
            }).order_by("pk").values())
            for model in DOMAIN_MODELS}


def mutation_world(kind, native, monkeypatch):
    space, _manager, donor = setup("cx14-mutation", "finance.sponsors", "billing.offline_claims")
    set_mode(space, "donations", OFFLINE)
    switch(space, "billing.maker_checker", on=False)
    actor = staff("cx14-mutation", space, "fundraising")
    api = client_for(actor, space, native)
    release = Mock()
    monkeypatch.setattr("apps.payments.donations.views_sponsor_logo.images.release_public_image_on_commit", release)
    monkeypatch.setattr("apps.payments.notifications_l5.notify_claim", lambda *_args: None)
    if kind == "logo":
        row = Sponsor.objects.create(makerspace=space, name="Retained sponsor", created_by=actor,
                                     logo_key=f"sponsor/{space.pk}/retained.png")
        url = reverse("admin-sponsor-logo", kwargs={"makerspace_id": space.pk, "pk": row.pk})
        return space, api, row, None, None, release, "delete", url
    identity = Donor(account=donor, actor=donor, name="Retained giver", email=donor.email)
    row, payment = create_gift(space, identity, amount=Decimal("25.00"))
    claim = submit_claim(payment, claimant=donor, reference="CX14-CLAIM", paid_on=local_now(space).date())
    return space, api, row, payment, claim, release, "post", admin(space, f"/{row.pk}/claim/{kind}")


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["finance.donations", "finance.sponsors"])
def test_logo_delete_off_on_retains_rows_and_never_schedules_release_while_off(native, key, monkeypatch):
    space, api, sponsor, _, _, release, method, url = mutation_world("logo", native, monkeypatch)
    before = snapshot(space)
    switch(space, key, on=False)
    audits = list(AuditLog.objects.filter(makerspace=space).order_by("pk").values())
    with no_domain_writes():
        refused = getattr(api, method)(url, {}, format="json")
    assert refused.status_code == 404, refused.content
    assert refused.json()["code"] == "feature_disabled"
    assert snapshot(space) == before
    assert list(AuditLog.objects.filter(makerspace=space).order_by("pk").values()) == audits
    release.assert_not_called()
    switch(space, key)
    restored = api.delete(url)
    assert restored.status_code == 200, restored.content
    sponsor.refresh_from_db()
    assert sponsor.logo_key == ""
    assert release.call_count == 1
    assert release.call_args.args[1] == f"sponsor/{space.pk}/retained.png"
    assert AuditLog.objects.filter(makerspace=space, action="sponsor.logo_removed").count() == 1
    assert api.delete(url).status_code == 200
    assert release.call_count == 1
    assert AuditLog.objects.filter(makerspace=space, action="sponsor.logo_removed").count() == 1


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["finance.donations", "billing.offline_claims"])
@pytest.mark.parametrize("decision", ["confirm", "reject"])
def test_claim_decision_off_on_preserves_claim_debt_receipts_and_audit(
        native, key, decision, monkeypatch, django_capture_on_commit_callbacks):
    space, api, donation, payment, claim, _, method, url = mutation_world(decision, native, monkeypatch)
    before = snapshot(space)
    switch(space, key, on=False)
    audits = list(AuditLog.objects.filter(makerspace=space).order_by("pk").values())
    with no_domain_writes():
        refused = getattr(api, method)(url, {"note": "Reviewed transfer"}, format="json")
    assert refused.status_code == 404, refused.content
    assert refused.json()["code"] == "feature_disabled"
    assert snapshot(space) == before
    assert list(AuditLog.objects.filter(makerspace=space).order_by("pk").values()) == audits
    switch(space, key)
    with django_capture_on_commit_callbacks(execute=True):
        restored = api.post(url, {"note": "Reviewed transfer"}, format="json")
    assert restored.status_code == 200, restored.content
    claim.refresh_from_db()
    payment.refresh_from_db()
    donation.refresh_from_db()
    confirmed = decision == "confirm"
    assert claim.status == ("confirmed" if confirmed else "rejected")
    assert payment.status == ("paid_offline" if confirmed else "pending")
    assert donation.status == ("paid" if confirmed else "pending")
    receipts = ManualSettlement.objects.filter(payment=payment)
    assert receipts.count() == (1 if confirmed else 0)
    if confirmed:
        receipt = receipts.get()
        assert (receipt.method, receipt.reference, receipt.amount, receipt.currency) == (
            "upi", "CX14-CLAIM", Decimal("25.00"), payment.currency)
        assert AuditLog.objects.filter(makerspace=space, action="payment.paid_offline").count() == 1
    action = "payment.paid_claim_confirmed" if confirmed else "payment.paid_claim_rejected"
    assert AuditLog.objects.filter(makerspace=space, action=action).count() == 1
    after = snapshot(space)
    with no_domain_writes():
        replay = api.post(url, {}, format="json")
    assert replay.status_code == 404, replay.content
    assert replay.json()["code"] == "no_open_claim"
    assert snapshot(space) == after
    assert AuditLog.objects.filter(makerspace=space, action=action).count() == 1


def test_core_ledger_can_still_settle_existing_gift_with_donation_area_off(monkeypatch):
    space, api, donation, payment, claim, _, _, _ = mutation_world("confirm", False, monkeypatch)
    switch(space, "finance.donations", "billing.offline_claims", on=False)
    response = api.post(f"/api/v1/admin/makerspace/{space.pk}/payments/{payment.pk}/mark-offline",
                        settlement_payload(reference="CX14-CORE"), format="json")
    assert response.status_code == 200, response.content
    payment.refresh_from_db()
    assert payment.status == "paid_offline"
    receipt = ManualSettlement.objects.get(payment=payment)
    assert (receipt.method, receipt.reference, receipt.amount) == ("cash", "CX14-CORE", Decimal("25.00"))
    assert AuditLog.objects.filter(makerspace=space, action="payment.paid_offline").count() == 1
