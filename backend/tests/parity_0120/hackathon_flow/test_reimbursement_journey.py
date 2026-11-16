"""Decision 296 review: the reimbursement read contract the member and staff consoles depend on.

The member page drives every step from `allowed_actions`, and the staff console pins every version a
finance decision checks. These tests read the projections exactly as the views return them.
"""
from datetime import date, timedelta

import pytest
from django.utils import timezone

from apps.event_reimbursements import claim_workflow, direct_booking
from apps.event_reimbursements.models import ReimbursementClaim
from apps.event_reimbursements.projections import claim_detail, member_summary, request_detail
from apps.event_reimbursements.request_form_adapter import context
from apps.payments.event_payouts.errors import PayoutError
from tests.event_reimbursements.conftest import cmd, make_world, world  # noqa: F401 (fixtures)
from tests.event_reimbursements.helpers import accepted, decision_data, requested, submitted

pytestmark = pytest.mark.django_db(transaction=True)  # the reimbursement commands take domain fences and need real commits


def test_the_request_form_context_carries_currency_categories_and_distance_rule(world):
    value = context(world.programme)
    assert value["currency"] == world.programme.currency
    assert value["allowed_categories"] == list(world.programme.allowed_categories)
    assert "min_distance_km" in value


def test_a_new_member_may_start_and_submit_a_request(world):
    actions = member_summary(world.event, world.owner)["allowed_actions"]
    assert "create_request" in actions and "submit_request" in actions


def test_a_submitted_request_may_be_withdrawn_and_offers_no_claim_before_an_award(world):
    requested(world)
    actions = member_summary(world.event, world.owner)["allowed_actions"]
    assert "withdraw_request" in actions and "create_claim" not in actions and "submit_request" not in actions


def test_after_the_event_an_accepted_award_offers_create_claim(world, monkeypatch):
    award = accepted(world)
    assert award.state == "accepted"
    after = world.event.ends_at + timedelta(days=1)
    assert after < world.programme.claim_due_at
    monkeypatch.setattr(timezone, "now", lambda: after)
    actions = member_summary(world.event, world.owner)["allowed_actions"]
    assert "create_claim" in actions


def test_staff_request_rows_name_the_person_and_open_the_decision(world):
    grant = requested(world)
    row = request_detail(grant, sensitive=True, screening=True)
    assert row["owner_label"] and row["allowed_actions"] == ["decide"]
    assert row["budget"]["pool_version"] == world.pool.version and row["tiers"] == []


def test_staff_claim_review_pins_every_decision_version(world, monkeypatch):
    claim, _, line_id = submitted(world, monkeypatch)
    finance = claim_detail(claim, finance=True)
    assert finance["current_revision"] == claim.current_revision_id
    assert finance["decision_sequence"] == 0 and finance["pool_version"] == claim.award.pool.version
    assert finance["eligibility_revision"] == claim.award.request.registration.attendance_revision
    assert finance["claimed_minor"] == claim.current_revision.total_minor
    assert finance["accepted_cap_minor"] == claim.award.amount_minor
    assert finance["review_lines"][0]["receipt_asset_id"] and finance["review_lines"][0]["vendor"]
    # A body built only from those fields is accepted by the finance decision.
    data = decision_data(world, claim, line_id, claim.current_revision.total_minor)
    assert data["expected_pool_version"] == finance["pool_version"]
    assert data["eligibility_revision"] == finance["eligibility_revision"]
    assert data["expected_decision_sequence"] == finance["decision_sequence"]


def test_screeners_see_no_receipt_asset_or_vendor(world, monkeypatch):
    claim, _, _ = submitted(world, monkeypatch)
    screening = claim_detail(claim, finance=False)
    line = screening["review_lines"][0]
    assert "receipt_asset_id" not in line and "vendor" not in line
    assert screening["appeal_statement"] is None and "recommend" in screening["allowed_actions"]


def test_travel_the_space_booked_directly_never_takes_a_claim(world, monkeypatch):
    grant = requested(world)
    world.pool.refresh_from_db()
    direct_booking.record(request=world.finance, event_id=world.event.pk, request_id=grant.pk, data=cmd(
        grant.version, expected_pool_version=world.pool.version, amount_minor=8000, currency="INR", vendor="Rail",
        booked_on=date(2026, 11, 1), method="bank_transfer", reference="PNR-1"))
    after = world.event.ends_at + timedelta(days=1)
    monkeypatch.setattr(timezone, "now", lambda: after)
    assert "create_claim" not in member_summary(world.event, world.owner)["allowed_actions"]
    from tests.accounts.test_reauthentication import request as session_request
    member_session = session_request(world.owner, surface="member")  # made after the clock moved, so not expired
    with pytest.raises(PayoutError) as caught:
        claim_workflow.save_draft(event_id=world.event.pk, actor=world.owner, request=member_session,
                                  data=cmd(0, lines=[]))
    assert caught.value.detail["code"] in ("direct_booking_no_claim", "claim_closed")
    assert not ReimbursementClaim.objects.filter(event=world.event).exists()
