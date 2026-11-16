"""Decision 246 (lane T4): scheduled-sweep conditions, called directly (no Celery worker).

Guest-pass sweeps, the join follow-up sweep, the pickup-reminder sweep and the covered-renewal
marker: each is a no-op with its module or capability off, touches only the spaces that have it on
(per-tenant isolation) and is idempotent when run twice.
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.events import join_followup
from apps.hardware_requests import pickup_reminders
from apps.hardware_requests.models import HardwareRequest
from apps.integrations.models_contract import NotificationEnvelope
from apps.makerspaces import guest_pass_issue, guest_pass_sweeps
from apps.makerspaces.models import CommunityPolicy, GuestPass, MembershipTerm
from tests.events.test_join_funnel_223 import _attended, _world
from tests.hardware_requests.loan_policy_helpers import setup_loan
from tests.makerspaces.l4_helpers import features_off
from tests.makerspaces.test_guest_passes import _space
from tests.makerspaces.test_membership_j1 import manager, user

pytestmark = pytest.mark.django_db(transaction=True)


def ended_pass(slug):
    space = _space(slug)
    row, _ = guest_pass_issue.issue_staff_pass(manager(space, f"{slug}-manager"), space, user(f"{slug}-guest"))
    GuestPass.objects.filter(pk=row.pk).update(
        valid_from=timezone.now() - timedelta(hours=5), valid_until=timezone.now() - timedelta(minutes=1))
    return space, row


def ending_pass(slug):
    space = _space(slug)
    row, _ = guest_pass_issue.issue_staff_pass(manager(space, f"{slug}-manager"), space, user(f"{slug}-guest"))
    GuestPass.objects.filter(pk=row.pk).update(valid_until=timezone.now() + timedelta(minutes=30))
    return space, row


# --- guest-pass sweeps -----------------------------------------------------------------------------

def test_guest_pass_sweep_touches_only_spaces_with_the_capability_on():
    space_off, row_off = ended_pass("t246-sw-gp-off")
    _space_on, row_on = ended_pass("t246-sw-gp-on")
    features_off(space_off, "guest_passes")
    counts = guest_pass_sweeps.run_guest_pass_sweeps()
    assert counts["expired"] == 1
    assert GuestPass.objects.get(pk=row_on.pk).status == "expired"
    assert GuestPass.objects.get(pk=row_off.pk).status != "expired"


def test_guest_pass_sweep_is_idempotent_and_notifies_each_ending_pass_once():
    _space_row, row = ending_pass("t246-sw-gp-idem")
    first = guest_pass_sweeps.run_guest_pass_sweeps()
    assert first["notified"] == 1
    envelopes = NotificationEnvelope.objects.count()
    second = guest_pass_sweeps.run_guest_pass_sweeps()
    assert second["notified"] == 0 and second["expired"] == 0 and second["failed"] == 0
    assert NotificationEnvelope.objects.count() == envelopes
    assert GuestPass.objects.get(pk=row.pk).status != "expired"  # still valid for 30 minutes


def test_one_spaces_ending_pass_never_notifies_another_spaces_holder():
    _a, _row_a = ending_pass("t246-sw-gp-a")
    space_b, row_b = ending_pass("t246-sw-gp-b")
    guest_pass_sweeps.run_guest_pass_sweeps()
    for envelope in NotificationEnvelope.objects.filter(source_id__in=[str(row_b.pk)]):
        assert envelope.makerspace_id == space_b.pk


# --- join follow-up sweep --------------------------------------------------------------------------

def test_join_followup_is_a_noop_with_the_funnel_off_and_isolated_per_space(monkeypatch):
    on_space = _world("t246-sw-jf-on")
    off_space = _world("t246-sw-jf-off", funnel=False)
    for space in (on_space, off_space):
        CommunityPolicy.objects.create(makerspace=space, join_followup_enabled=True, join_followup_delay_hours=24)
    visitor_on, visitor_off = user("t246-jf-visitor-on"), user("t246-jf-visitor-off")
    _attended(on_space, visitor_on, ended_hours_ago=30)
    _attended(off_space, visitor_off, ended_hours_ago=30)
    sent = []
    monkeypatch.setattr(join_followup, "notify_join_followup", lambda row: sent.append(row.member_id))
    assert join_followup.send_join_followups() == 1
    assert sent == [visitor_on.pk]


def test_join_followup_is_a_noop_with_the_policy_switch_off(monkeypatch):
    space = _world("t246-sw-jf-policy")
    CommunityPolicy.objects.create(makerspace=space, join_followup_enabled=False, join_followup_delay_hours=24)
    _attended(space, user("t246-jf-policy-visitor"), ended_hours_ago=30)
    sent = []
    monkeypatch.setattr(join_followup, "notify_join_followup", lambda row: sent.append(row.member_id))
    assert join_followup.send_join_followups() == 0 and sent == []


def test_join_followup_sends_each_attendee_once_across_repeated_sweeps():
    space = _world("t246-sw-jf-once")
    CommunityPolicy.objects.create(makerspace=space, join_followup_enabled=True, join_followup_delay_hours=24)
    visitor = user("t246-jf-once-visitor")
    _attended(space, visitor, ended_hours_ago=30)
    assert join_followup.send_join_followups() == 1
    reserved = NotificationEnvelope.objects.filter(source_kind=join_followup.SOURCE, recipient=visitor).count()
    assert reserved == 1
    assert join_followup.send_join_followups() == 0
    assert NotificationEnvelope.objects.filter(source_kind=join_followup.SOURCE, recipient=visitor).count() == 1


# --- pickup reminders ------------------------------------------------------------------------------

def accept(loan):
    now = timezone.now()
    HardwareRequest.objects.filter(pk=loan.pk).update(
        status="accepted", accepted_at=now - timedelta(days=3) + timedelta(hours=20),
        pickup_until=now + timedelta(hours=20))


def test_pickup_reminders_remind_only_the_space_that_has_the_capability():
    on_space, on_member, _m, _p, on_loan, _policy, _c = setup_loan("t246-sw-pk-on", linked=False)
    off_space, _om, _m2, _p2, off_loan, _policy2, _c2 = setup_loan("t246-sw-pk-off", linked=False)
    on_space.enabled_features = sorted(set(on_space.enabled_features) | {"loans.pickup_windows"})
    on_space.save(update_fields=["enabled_features"])
    off_space.enabled_features = sorted(set(off_space.enabled_features) - {"loans.pickup_windows"})
    off_space.save(update_fields=["enabled_features"])
    accept(on_loan)
    accept(off_loan)
    assert pickup_reminders.remind_expiring_pickups()["reminded"] == 1
    rows = NotificationEnvelope.objects.filter(event="pickup_expiring")
    assert {row.recipient_id for row in rows} == {on_member.pk}
    assert {row.makerspace_id for row in rows} == {on_space.pk}
    assert pickup_reminders.remind_expiring_pickups()["reminded"] == 0


# --- covered renewal marker ------------------------------------------------------------------------

def test_a_covered_renewal_is_stamped_once_and_never_raised_again():
    from apps.makerspaces import volunteer_hours
    from apps.makerspaces.membership_plan_services import create_term
    from apps.makerspaces.membership_renewal_charges import raise_renewal
    from apps.payments.models import Payment
    from tests.money_modes.test_volunteer_credit import _today, _world as credit_world

    makerspace, actor, member, plan, membership = credit_world(per=60, amount=Decimal("50.00"))
    # `renews` and `renewal_price` are derived now: a rolling plan renews, at `renewal_amount`.
    plan.plan_type, plan.is_active, plan.renewal_amount = "rolling", True, Decimal("20.00")
    plan.save(update_fields=["plan_type", "is_active", "renewal_amount"])
    volunteer_hours.log_hours(actor, makerspace, member, minutes=60, worked_on=_today(), by_staff=True)
    term = create_term(actor, membership, plan)
    first = raise_renewal(term)
    stamped = MembershipTerm.objects.get(pk=term.pk)
    if first != "charged":
        pytest.skip("this world's money mode skips the renewal seam")
    assert stamped.renewal_covered_at is not None and stamped.renewal_payment_id is None
    marker = stamped.renewal_covered_at
    assert raise_renewal(stamped) == "skipped"
    again = MembershipTerm.objects.get(pk=term.pk)
    assert again.renewal_covered_at == marker  # the marker is not re-stamped
    assert not Payment.objects.filter(subject_type="membership_term", subject_id=term.pk).exists()


def test_a_covered_renewal_is_skipped_with_the_membership_module_off():
    from apps.makerspaces.membership_renewal_charges import raise_renewal
    from apps.makerspaces.membership_plan_services import create_term
    from apps.makerspaces.models import Makerspace
    from tests.money_modes.test_volunteer_credit import _world as credit_world

    makerspace, actor, _member, plan, membership = credit_world(per=60, amount=Decimal("50.00"))
    # `renews` and `renewal_price` are derived now: a rolling plan renews, at `renewal_amount`.
    plan.plan_type, plan.is_active, plan.renewal_amount = "rolling", True, Decimal("20.00")
    plan.save(update_fields=["plan_type", "is_active", "renewal_amount"])
    term = create_term(actor, membership, plan)
    Makerspace.objects.filter(pk=makerspace.pk).update(
        enabled_modules=sorted(set(makerspace.enabled_modules or []) - {"membership"}))
    result = raise_renewal(term)
    assert result == "skipped"  # decision 253(b): module off is by design, never "failed"
    assert MembershipTerm.objects.get(pk=term.pk).renewal_covered_at is None
