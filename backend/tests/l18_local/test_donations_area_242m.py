"""Decision 242(m): the Space Manager runs donations, may delegate to Fundraising, and no area manager sees them."""

import pytest
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.payments.finance_scope import finance_view
from apps.payments.models import Donation
from tests.l18_local.helpers import admin, charge_for, client, gift, settle_offline, setup, staff, switch

pytestmark = pytest.mark.django_db
AREA_ROLES = ("inventory_manager", "machine_manager", "event_manager", "booking_manager", "shop_manager",
              "handover", "technician")


def test_fundraising_runs_the_donations_area():
    space, manager, donor = setup("fr-run", "finance.recurring_donations")
    fundraiser = staff("fr-run", space, "fundraising")
    donation, _ = gift(space, donor, amount="300", recognize_publicly=True)
    assert client(fundraiser).get(admin(space)).status_code == 200
    assert client(fundraiser).get(admin(space, "/campaigns")).status_code == 200
    assert client(fundraiser).get(admin(space, "/pledges")).status_code == 200
    created = client(fundraiser).post(admin(space, "/campaigns"), {"name": "Roof", "slug": "roof"}, format="json")
    assert created.status_code == 201, created.content
    # The gift's owner settles it: subject authority is manage_donations (no record_payment grant).
    settle_offline(fundraiser, charge_for(donation))
    donation.refresh_from_db()
    assert donation.status == Donation.Status.PAID
    donors = client(fundraiser).get(admin(space, "/donors")).json()
    assert donors[0]["gift_count"] == 1 and donors[0]["recognize_publicly"] is True
    assert "pan" not in str(donors[0]).lower()
    resent = client(fundraiser).post(admin(space, f"/{donation.pk}/receipt/reissue"))
    assert resent.status_code == 200
    assert AuditLog.objects.filter(makerspace=space, action="donation.receipt_reissued").exists()
    view = finance_view(fundraiser, space.pk)
    assert not view.everything and view.domains == frozenset({"donations"})


def test_reissue_refuses_a_gift_not_yet_received():
    space, manager, donor = setup("fr-pending")
    donation, _ = gift(space, donor)
    refused = client(manager).post(admin(space, f"/{donation.pk}/receipt/reissue"))
    assert refused.status_code == 400 and refused.json()["code"] == "donation_not_received"


def test_export_is_csv_without_tax_identity_and_audited():
    space, manager, donor = setup("fr-export")
    gift(space, donor, amount="120")
    response = client(manager).get(admin(space, "/export.csv"))
    assert response.status_code == 200 and response["Content-Type"].startswith("text/csv")
    body = response.content.decode()
    header = body.splitlines()[0]
    assert "donor_email" in header and "pan" not in header and "address" not in header
    assert AuditLog.objects.filter(makerspace=space, action="donation.exported", meta__rows=1).exists()


@pytest.mark.parametrize("role", AREA_ROLES)
def test_no_area_manager_reaches_donations(role):
    space, manager, donor = setup(f"fr-area-{role[:6]}")
    other = staff(f"fr-area-{role[:6]}", space, role)
    for tail in ("", "/campaigns", "/donors", "/export.csv", "/settings"):
        assert client(other).get(admin(space, tail)).status_code == 404, tail
    view = finance_view(other, space.pk)
    assert not view.sees("donations") and not view.may_record("donations")


def test_area_overview_finance_never_shows_donations_to_an_area_manager():
    from apps.operations.area_overview_finance import visible_areas

    space, manager, donor = setup("fr-overview")
    for role in AREA_ROLES:
        assert "donations" not in visible_areas(finance_view(staff("fr-overview", space, role), space.pk)), role
    assert "donations" in visible_areas(finance_view(manager, space.pk))


def test_area_queue_never_lists_gifts_for_an_area_manager():
    from apps.payments.area_queue import area_payments

    space, manager, donor = setup("fr-queue")
    donation, _ = gift(space, donor)
    payment = charge_for(donation)
    for role in ("inventory_manager", "event_manager", "shop_manager"):
        other = staff("fr-queue", space, role)
        assert not area_payments(other, space.pk).filter(pk=payment.pk).exists(), role


def test_donation_reports_admit_fundraising():
    from apps.operations.report_registry import REPORT_REGISTRY
    from apps.operations.report_subjects import report_action_allowed
    from tests.gap_donations_local.helpers import analytics, report_space

    space, manager, donor = report_space("fr-reports")
    fundraiser = staff("fr-reports", space, "fundraising")
    assert report_action_allowed(fundraiser, REPORT_REGISTRY["donations-campaign-progress"], space.pk)
    assert analytics(fundraiser, space, "donations-campaign-progress").status_code == 200


def test_fundraising_is_not_organization_grantable_and_holds_no_other_money():
    from apps.accounts import rbac
    from apps.makerspaces.role_catalog import ROLE_BY_SLUG

    assert "manage_donations" not in rbac.ORGANIZATION_GRANTABLE_ACTIONS
    assert ROLE_BY_SLUG["fundraising"].combinable
    effective = rbac.expand_implied_actions(ROLE_BY_SLUG["fundraising"].granted_actions)
    assert effective == {"manage_donations"}
    assert "manage_donations" in rbac.expand_implied_actions({"manage_makerspace"})


def test_switch_off_closes_the_area_to_fundraising_too():
    space, manager, donor = setup("fr-off")
    fundraiser = staff("fr-off", space, "fundraising")
    switch(space, "finance.donations", on=False)
    assert client(fundraiser).get(admin(space, "/donors")).status_code == 404
    assert APIClient().get(f"/api/v1/bootstrap?slug={space.slug}").json()["makerspace"].get("donate_enabled") is None
