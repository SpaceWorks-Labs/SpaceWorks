"""RP-3: what each donations report counts (builders called directly)."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.operations.reports import report_data
from apps.payments.donations.pledges import raise_period
from apps.payments.donations.reports import build_campaign_progress, build_pledges
from apps.payments.donations.reports_sponsors import build_sponsor_perks
from apps.payments.models import Donation, DonationPledge, Sponsor, SponsorPerk, SponsorTier
from apps.payments.reconciliation import mark_offline
from tests.gap_donations_local.helpers import campaign, client, gift, paid_gift, report_space, rows_as_dicts
from tests.l18_local.helpers import charge_for, settle_offline
from tests.return_helpers import settlement_details

pytestmark = pytest.mark.django_db


def _pledge(space, donor, **extra):
    response = client(donor).post(f"/api/v1/public/{space.slug}/donations/pledges",
                                  {"amount": "200", "interval": "monthly", **extra}, format="json")
    assert response.status_code == 201, response.content
    return DonationPledge.objects.get(pk=response.json()["id"])


# A gift becomes PAID in an on_commit hook, so a test that settles one needs real commits.
@pytest.mark.django_db(transaction=True)
def test_campaign_progress_counts_paid_money_against_the_goal():
    space, manager, donor = report_space("rp3-camp", "finance.recurring_donations")
    laser = campaign(space)
    paid_gift(space, manager, donor, "300.00", campaign=laser.pk)
    paid_gift(space, manager, donor, "200.00", campaign=laser.pk)
    gift(space, donor, amount="50.00", campaign=laser.pk)  # still waiting for payment
    paid_gift(space, manager, donor, "75.00")  # general fund
    _pledge(space, donor, campaign=laser.pk)
    rows = {row["campaign"]: row for row in build_campaign_progress(space.pk).records}
    laser_row = rows["New laser"]
    assert laser_row["raised_amount"] == Decimal("500.00") and laser_row["goal_amount"] == Decimal("1000.00")
    assert laser_row["pending_amount"] == Decimal("50.00") and laser_row["gift_count"] == 2
    assert laser_row["donor_count"] == 1  # one signed-in giver, two gifts
    assert laser_row["percent_of_goal"] == Decimal("50.0") and laser_row["status"] == "open"
    assert laser_row["active_pledges"] == 1 and laser_row["pledged_per_month"] == Decimal("200.00")
    general = rows["General fund (no campaign)"]
    assert general["campaign_id"] is None and general["raised_amount"] == Decimal("75.00")
    assert general["goal_amount"] is None and general["percent_of_goal"] is None


def test_a_campaign_with_no_gifts_still_shows_and_its_window_sets_the_status():
    space, manager, donor = report_space("rp3-camp-status")
    now = timezone.now()
    campaign(space, name="Later", slug="later", starts_at=now + timedelta(days=5))
    campaign(space, name="Past", slug="past", starts_at=now - timedelta(days=9), ends_at=now - timedelta(days=1))
    campaign(space, name="Off", slug="off", is_active=False)
    rows = {row["campaign"]: row for row in build_campaign_progress(space.pk).records}
    assert rows["Later"]["status"] == "scheduled" and rows["Later"]["raised_amount"] == Decimal("0.00")
    assert rows["Past"]["status"] == "ended" and rows["Off"]["status"] == "inactive"


# A gift becomes PAID in an on_commit hook, so a test that settles one needs real commits.
@pytest.mark.django_db(transaction=True)
def test_campaign_progress_date_range_counts_money_received_inside_it():
    space, manager, donor = report_space("rp3-camp-range")
    laser = campaign(space)
    old = paid_gift(space, manager, donor, "100.00", campaign=laser.pk)
    Donation.objects.filter(pk=old.pk).update(paid_at=timezone.now() - timedelta(days=40))
    paid_gift(space, manager, donor, "60.00", campaign=laser.pk)
    window = (timezone.now() - timedelta(days=7), timezone.now() + timedelta(days=1))
    row = next(r for r in build_campaign_progress(space.pk, date_range=window).records if r["campaign_id"] == laser.pk)
    assert row["raised_amount"] == Decimal("60.00") and row["gift_count"] == 1


# A gift becomes PAID in an on_commit hook, so a test that settles one needs real commits.
@pytest.mark.django_db(transaction=True)
def test_pledges_split_active_missed_paused_and_cancelled():
    space, manager, donor = report_space("rp3-pledges", "finance.recurring_donations")
    today = timezone.localdate()
    up_to_date = _pledge(space, donor)
    first = raise_period(up_to_date, today)
    settle_offline(manager, charge_for(first), reference="PLEDGE-1")
    behind = _pledge(space, donor, amount="300")
    stale = raise_period(behind, today)
    Donation.objects.filter(pk=stale.pk).update(period_start=today - timedelta(days=70))  # a period long over
    paused = _pledge(space, donor, amount="90")
    DonationPledge.objects.filter(pk=paused.pk).update(status="paused")
    cancelled = _pledge(space, donor, amount="40", interval="yearly")
    DonationPledge.objects.filter(pk=cancelled.pk).update(status="cancelled")
    rows = {row["pledge_state"]: row for row in build_pledges(space.pk).records}
    assert set(rows) == {"active", "missed", "paused", "cancelled"}
    assert rows["active"]["pledge_count"] == 1 and rows["active"]["paid_periods"] == 1
    assert rows["active"]["paid_amount"] == Decimal("200.00") and rows["active"]["missed_periods"] == 0
    assert rows["missed"]["missed_periods"] == 1 and rows["missed"]["outstanding_amount"] == Decimal("300.00")
    assert rows["paused"]["amount_per_period"] == Decimal("90.00")
    assert rows["cancelled"]["interval"] == "yearly" and rows["cancelled"]["monthly_equivalent"] == Decimal("3.33")


def test_sponsor_perks_are_overdue_due_open_or_fulfilled():
    space, manager, donor = report_space("rp3-perks", "finance.sponsors")
    today = timezone.localdate()
    tier = SponsorTier.objects.create(makerspace=space, name="Gold", rank=1)
    sponsor = Sponsor.objects.create(makerspace=space, name="Acme Robotics", tier=tier,
                                     contact_email="rita@acme.example", contact_name="Rita Contact")
    SponsorPerk.objects.create(makerspace=space, tier=tier, description="Template perk")  # never a row
    late = SponsorPerk.objects.create(makerspace=space, sponsor=sponsor, description="Logo on banner",
                                      due_on=today - timedelta(days=4))
    SponsorPerk.objects.create(makerspace=space, sponsor=sponsor, description="Talk slot", due_on=today + timedelta(days=9))
    SponsorPerk.objects.create(makerspace=space, sponsor=sponsor, description="Thank-you post")
    SponsorPerk.objects.create(makerspace=space, sponsor=sponsor, description="Booth", due_on=today,
                               fulfilled_at=timezone.now(), fulfilled_by=manager)
    rows = build_sponsor_perks(space.pk).records
    assert [row["state"] for row in rows] == ["overdue", "due", "open", "fulfilled"]
    assert rows[0]["perk_id"] == late.pk and rows[0]["days_overdue"] == 4 and rows[0]["tier"] == "Gold"
    assert rows[0]["sponsor"] == "Acme Robotics" and rows[3]["fulfilled_on"] == today
    assert all("Template perk" != row["perk"] for row in rows)


def test_finance_donations_area_holds_only_donations_money():
    space, manager, donor = report_space("rp3-area")
    paid_gift(space, manager, donor, "250.00")
    from tests.l5_local.helpers import dues
    mark_offline(dues(space, donor, "40.00"), manager, settlement_details(reference="CASH-RP3"))
    area = rows_as_dicts(report_data("finance-donations", space.pk, actor=manager))
    assert area and {row["domain"] for row in area} == {"donations"}
    assert sum(Decimal(row["money_in"]) for row in area) == Decimal("250.00")
    everything = rows_as_dicts(report_data("income-spending", space.pk, actor=manager))
    assert {"donations", "membership"} <= {row["domain"] for row in everything}
