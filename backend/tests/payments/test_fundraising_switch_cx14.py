"""Decision 550: the fundraising master refuses writes and restores retained data."""

import pytest
from django.db import connection
from django.urls import reverse
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.makerspaces.capabilities import default_enabled_features
from apps.makerspaces.platform import feature_enabled
from apps.payments.donations.gates import donation_write
from apps.payments.donations.models import Donation, DonationCampaign, Sponsor
from apps.payments.models import Payment
from tests.l18_local.helpers import admin, gift, setup, staff, switch
from tests.modules.switch_matrix_object_helpers import _no_write, client_for, no_domain_writes

pytestmark = pytest.mark.django_db


def test_master_is_opt_in_and_sponsor_choice_is_dormant_while_off():
    assert "finance.donations" not in default_enabled_features()
    space, _manager, _donor = setup("cx14-default", "finance.sponsors")
    switch(space, "finance.donations", on=False)
    assert "finance.sponsors" in space.enabled_features
    assert feature_enabled(space, "finance.sponsors") is False
    switch(space, "finance.donations")
    assert feature_enabled(space, "finance.sponsors") is True


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("kind", ["campaign", "sponsor", "gift"])
def test_off_refuses_before_domain_write_and_on_restores(native, kind):
    space, _manager, _donor = setup("cx14-switch", "finance.sponsors")
    switch(space, "billing.maker_checker", on=False)
    actor = staff("cx14-switch", space, "fundraising")
    client = client_for(actor, space, native)
    sponsor = Sponsor.objects.create(makerspace=space, name="Retained", created_by=actor)
    campaign = DonationCampaign.objects.create(makerspace=space, name="Retained", slug="retained", currency="inr")
    before = (Donation.objects.count(), Payment.objects.count(), Sponsor.objects.count(), DonationCampaign.objects.count())
    switch(space, "finance.donations", on=False)
    audit_count = AuditLog.objects.filter(makerspace=space).count()
    if kind == "campaign":
        url, data, action = admin(space, "/campaigns"), {"name": "New", "slug": "new"}, "donation.campaign_created"
    elif kind == "sponsor":
        url = reverse("admin-sponsors", kwargs={"makerspace_id": space.pk})
        data, action = {"name": "New sponsor"}, "sponsor.created"
    else:
        url = admin(space)
        data = {"donor_name": "Giver", "donor_email": "giver@example.test", "amount": "25",
                "settlement": {"method": "cash", "reference": "CX14", "received_at": "2026-11-14T10:00:00Z"}}
        action = "donation.created"
    with no_domain_writes():
        refused = client.post(url, data, format="json")
    assert refused.status_code == 404, refused.content
    assert refused.json()["code"] == "feature_disabled"
    assert (Donation.objects.count(), Payment.objects.count(), Sponsor.objects.count(), DonationCampaign.objects.count()) == before
    assert AuditLog.objects.filter(makerspace=space).count() == audit_count
    assert Sponsor.objects.get(pk=sponsor.pk).name == "Retained"
    assert DonationCampaign.objects.get(pk=campaign.pk).name == "Retained"
    switch(space, "finance.donations")
    restored = client.post(url, data, format="json")
    assert restored.status_code == 201, restored.content
    assert AuditLog.objects.filter(makerspace=space, action=action).count() == 1


def test_public_gift_refuses_off_even_for_an_existing_pending_twin():
    space, _manager, donor = setup("cx14-replay")
    donation, _ = gift(space, donor, amount="25")
    switch(space, "finance.donations", on=False)
    from tests.l18_local.helpers import client, give_url

    before = AuditLog.objects.filter(makerspace=space).count()
    api = client(donor)
    with no_domain_writes():
        refused = api.post(give_url(space), {"amount": "25"}, format="json")
    assert refused.status_code == 404
    assert refused.json()["code"] == "feature_disabled"
    assert Donation.objects.filter(makerspace=space).count() == 1
    assert Payment.objects.filter(makerspace=space, subject_type="donation", subject_id=donation.pk).count() == 1
    assert AuditLog.objects.filter(makerspace=space).count() == before


def test_transaction_rechecks_fresh_switch_instead_of_a_stale_space_instance():
    from apps.makerspaces.guards import SurfaceOff

    space, _manager, _donor = setup("cx14-stale", "finance.sponsors")
    # Simulate a disable committed after the view's initial lookup.
    type(space).objects.filter(pk=space.pk).update(enabled_features=[])
    assert "finance.donations" in space.enabled_features
    with connection.execute_wrapper(_no_write), pytest.raises(SurfaceOff) as refused:
        with donation_write(space.pk):
            DonationCampaign.objects.create(makerspace=space, name="Forbidden", slug="forbidden", currency="inr")
    assert refused.value.status_code == 404
    assert refused.value.detail["code"] == "feature_disabled"
    assert not DonationCampaign.objects.filter(makerspace=space).exists()


def test_master_hides_public_sponsor_wall_and_retains_rows():
    space, manager, _donor = setup("cx14-wall", "finance.sponsors")
    sponsor = Sponsor.objects.create(makerspace=space, name="Public sponsor", created_by=manager, show_on_wall=True)
    url = reverse("public-sponsor-wall", kwargs={"makerspace_slug": space.slug})
    switch(space, "finance.donations", on=False)
    with no_domain_writes():
        refused = APIClient().get(url)
    assert refused.status_code == 404
    assert refused.json()["code"] == "feature_disabled"
    assert Sponsor.objects.filter(pk=sponsor.pk).exists()
    switch(space, "finance.donations")
    restored = APIClient().get(url)
    assert restored.status_code == 200
    assert [row["id"] for row in restored.json()["results"]] == [sponsor.pk]


def test_master_stops_pledge_and_sponsor_jobs_then_restores_once(monkeypatch):
    from decimal import Decimal
    from django.utils import timezone
    from apps.payments.donations.identity import Donor
    from apps.payments.donations.models import SponsorPerk
    from apps.payments.donations.pledges import create_pledge, due_pledge_ids, raise_one
    from apps.payments.donations.tasks import due_perk_ids, remind_perk

    space, manager, account = setup("cx14-jobs", "finance.sponsors", "finance.recurring_donations")
    monkeypatch.setattr("apps.payments.donations.notices.notify_pledge_due", lambda *_a, **_kw: None)
    monkeypatch.setattr("apps.payments.donations.notices.notify_perk_due", lambda *_a, **_kw: None)
    donor = Donor(account=account, actor=account, name="Giver", email=account.email)
    pledge = create_pledge(space, donor, amount=Decimal("25.00"), interval="monthly")
    today = timezone.localdate()
    sponsor = Sponsor.objects.create(makerspace=space, name="Sponsor", created_by=manager)
    perk = SponsorPerk.objects.create(makerspace=space, sponsor=sponsor, description="Thanks", due_on=today)
    switch(space, "finance.donations", on=False)
    before = AuditLog.objects.filter(makerspace=space).count()
    assert pledge.pk not in due_pledge_ids(100, today)
    assert perk.pk not in due_perk_ids(100, today)
    with connection.execute_wrapper(_no_write):
        assert raise_one(pledge.pk, today) is None
        assert remind_perk(perk.pk, today) is False
    pledge.refresh_from_db()
    perk.refresh_from_db()
    assert pledge.next_due_on == today and perk.reminded_on is None
    assert not Donation.objects.filter(makerspace=space).exists()
    assert not Payment.objects.filter(makerspace=space).exists()
    assert AuditLog.objects.filter(makerspace=space).count() == before
    switch(space, "finance.donations")
    assert raise_one(pledge.pk, today) is not None
    assert raise_one(pledge.pk, today) is None
    assert remind_perk(perk.pk, today) is True
    assert remind_perk(perk.pk, today) is False
    assert Donation.objects.filter(makerspace=space, pledge=pledge).count() == 1
    assert Payment.objects.filter(makerspace=space, subject_type="donation").count() == 1
    assert AuditLog.objects.filter(makerspace=space, action="pledge.period_raised").count() == 1


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
def test_sponsor_logo_refuses_off_before_storage_or_audit(native, monkeypatch):
    from unittest.mock import Mock

    space, _manager, _account = setup("cx14-logo", "finance.sponsors")
    actor = staff("cx14-logo", space, "fundraising")
    sponsor = Sponsor.objects.create(makerspace=space, name="Sponsor", created_by=actor)
    upload, finalize = Mock(), Mock()
    monkeypatch.setattr("apps.payments.donations.views_sponsor_logo.images.presigned_upload", upload)
    monkeypatch.setattr("apps.payments.donations.views_sponsor_logo.images.finalize_upload", finalize)
    api = client_for(actor, space, native)
    switch(space, "finance.donations", on=False)
    before = AuditLog.objects.filter(makerspace=space).count()
    url = reverse("admin-sponsor-logo", kwargs={"makerspace_id": space.pk, "pk": sponsor.pk})
    for method, body in (("post", {"filename": "logo.png", "content_type": "image/png"}),
                         ("put", {"object_key": f"sponsor/{space.pk}/logo.png"})):
        with no_domain_writes():
            refused = getattr(api, method)(url, body, format="json")
        assert refused.status_code == 404, refused.content
        assert refused.json()["code"] == "feature_disabled"
    upload.assert_not_called()
    finalize.assert_not_called()
    sponsor.refresh_from_db()
    assert sponsor.logo_key == ""
    assert AuditLog.objects.filter(makerspace=space).count() == before
