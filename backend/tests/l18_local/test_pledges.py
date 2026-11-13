"""L18 recurring donations: one charge per period, idempotent, no back-charging, switch off stops the job."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.payments.donations.pledges import due_pledge_ids, raise_one, raise_period
from apps.payments.donations.tasks import raise_pledges_task
from apps.payments.models import Donation, DonationPledge, Payment
from tests.l18_local.helpers import client, setup, switch

pytestmark = pytest.mark.django_db


def _pledge(space, donor, **extra):
    response = client(donor).post(f"/api/v1/public/{space.slug}/donations/pledges",
                                  {"amount": "200", "interval": "monthly", **extra}, format="json")
    assert response.status_code == 201, response.content
    return DonationPledge.objects.get(pk=response.json()["id"])


def test_pledges_need_their_own_switch():
    space, manager, donor = setup("pledge-off")
    refused = client(donor).post(f"/api/v1/public/{space.slug}/donations/pledges",
                                 {"amount": "200", "interval": "monthly"}, format="json")
    assert refused.status_code == 404
    switch(space, "finance.recurring_donations")
    assert _pledge(space, donor).status == "active"


def test_the_raise_is_idempotent_per_period_and_reminds_once():
    space, manager, donor = setup("pledge-raise", "finance.recurring_donations")
    pledge = _pledge(space, donor)
    today = timezone.localdate()
    first = raise_period(pledge, today)
    assert first is not None and first.period_start == today and first.source == "pledge"
    assert raise_period(pledge, today) is None  # same day again: nothing new
    pledge.refresh_from_db()
    assert pledge.next_due_on > today
    assert Donation.objects.filter(pledge=pledge).count() == 1
    payment = Payment.objects.get(subject_type="donation", subject_id=first.pk)
    assert payment.member == donor and payment.amount == pledge.amount
    assert AuditLog.objects.filter(action="pledge.period_raised").count() == 1


def test_missed_periods_are_skipped_never_back_charged():
    space, manager, donor = setup("pledge-skip", "finance.recurring_donations")
    pledge = _pledge(space, donor)
    long_ago = timezone.localdate() - timedelta(days=95)
    DonationPledge.objects.filter(pk=pledge.pk).update(starts_on=long_ago, next_due_on=long_ago)
    gift = raise_period(DonationPledge.objects.get(pk=pledge.pk), timezone.localdate())
    assert Donation.objects.filter(pledge=pledge).count() == 1
    assert gift.period_start > long_ago + timedelta(days=60)


def test_switch_off_or_a_paused_pledge_raises_nothing_and_keeps_the_rows():
    space, manager, donor = setup("pledge-pause", "finance.recurring_donations")
    pledge = _pledge(space, donor)
    switch(space, "finance.recurring_donations", on=False)
    assert raise_one(pledge.pk, timezone.localdate()) is None
    switch(space, "finance.recurring_donations")
    paused = client(donor).post(f"/api/v1/member/makerspaces/{space.pk}/pledges/{pledge.pk}", {"action": "pause"},
                                format="json")
    assert paused.status_code == 200 and paused.json()["status"] == "paused"
    assert raise_pledges_task() == 0 and not Donation.objects.exists()
    resumed = client(donor).post(f"/api/v1/member/makerspaces/{space.pk}/pledges/{pledge.pk}", {"action": "resume"},
                                 format="json")
    assert resumed.json()["status"] == "active"
    assert pledge.pk in due_pledge_ids(50, timezone.localdate())
    assert raise_pledges_task() == 1


def test_a_member_cannot_change_someone_elses_pledge_and_cancel_is_final():
    from tests.payments.account_helpers import make_payer
    space, manager, donor = setup("pledge-own", "finance.recurring_donations")
    pledge = _pledge(space, donor)
    other = make_payer("pledge-own-other", space)
    url = f"/api/v1/member/makerspaces/{space.pk}/pledges/{pledge.pk}"
    assert client(other).post(url, {"action": "cancel"}, format="json").status_code == 404
    assert client(donor).post(url, {"action": "cancel"}, format="json").json()["status"] == "cancelled"
    assert client(donor).post(url, {"action": "resume"}, format="json").status_code == 400
    assert AuditLog.objects.filter(action="pledge.cancelled").exists()


@pytest.mark.django_db(transaction=True)
def test_an_80g_pledge_shares_one_encrypted_tax_identity_with_every_period_gift():
    from tests.l18_local.helpers import tax_ready
    space, manager, donor = setup("pledge-80g", "finance.recurring_donations")
    tax_ready(space)
    pledge = _pledge(space, donor, wants_tax_receipt=True, donor_pan="ABCDE1234F", donor_address="4 Fort Rd")
    assert pledge.tax_detail_id and pledge.tax_detail.pan == "ABCDE1234F"
    gift = raise_period(DonationPledge.objects.get(pk=pledge.pk), timezone.localdate())
    assert gift.tax_detail_id == pledge.tax_detail_id and gift.wants_tax_receipt
    # A status-only change needs no tenant key: the PAN is not on the pledge row.
    from apps.payments.donations.pledges import change_pledge
    assert change_pledge(pledge, actor=donor, action="pause").status == "paused"
