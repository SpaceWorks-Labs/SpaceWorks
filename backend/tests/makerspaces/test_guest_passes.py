"""Decision 223: guest-pass core (policy, issue paths, limits, entitlements, day pass, lifecycle)."""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.makerspaces import guest_pass_day, guest_pass_issue, guest_pass_lifecycle, guest_pass_policy
from apps.makerspaces.guest_pass_policy import GuestPassError
from apps.makerspaces.guest_pass_queries import active_pass_for, pass_entitlements, require_waiver, visit_summary
from apps.makerspaces.models import (
    DayPassProduct, GuestPass, GuestPassPolicy, MakerspaceMembership, MakerspaceWaiver,
)
from apps.payments.models import Payment
from apps.payments.reconciliation import mark_offline
from tests.makerspaces.l4_helpers import features_on
from tests.makerspaces.test_membership_j1 import manager, member_role, space, user
from tests.return_helpers import settlement_details

pytestmark = pytest.mark.django_db(transaction=True)


def _space(slug="gp-space", *, charges=False, presence_required=False):
    makerspace = space(slug)
    makerspace.enabled_modules = sorted(set(makerspace.enabled_modules or []) | {"membership"})
    features = {"charges.enabled", "charges.membership"} if charges else set()
    makerspace.enabled_features = sorted(set(makerspace.enabled_features or []) | features)
    makerspace.save(update_fields=["enabled_modules", "enabled_features"])
    features_on(makerspace, "guest_passes", "day_passes")
    if not presence_required:
        GuestPassPolicy.objects.create(makerspace=makerspace, sponsor_must_be_present=False)
    return makerspace


def _sponsor(makerspace, name="sponsor", days=45):
    person = user(name)
    MakerspaceMembership.objects.create(
        makerspace=makerspace, user=person, assigned_role=member_role(makerspace), role="custom",
        status="active", activated_at=timezone.now() - timedelta(days=days))
    return person


def test_policy_defaults_match_decision_223_without_creating_a_row():
    makerspace = _space(presence_required=True)
    GuestPassPolicy.objects.filter(makerspace=makerspace).delete()
    policy = guest_pass_policy.policy_for(makerspace)
    assert (policy.guest_borrowing_mode, policy.guest_machine_mode, policy.sponsored_liability) == (
        "on_site", "none", "guest")
    assert policy.walk_in_registration_creates == "guest_pass" and policy.waiver_required_on_site is True
    assert (policy.sponsor_min_tenure_days, policy.max_concurrent_guests_per_sponsor,
            policy.visits_before_join_prompt) == (30, 2, 4)
    assert not GuestPassPolicy.objects.filter(makerspace=makerspace).exists()


def test_policy_update_is_audited_with_field_names_only_and_validates():
    makerspace = _space()
    actor = manager(makerspace)
    guest_pass_policy.update_policy(actor, makerspace, {"guest_borrowing_mode": "none", "hard_visit_cap": 9})
    entry = AuditLog.objects.get(makerspace=makerspace, action="makerspace.guest_pass_policy_updated")
    assert entry.meta == {"fields": ["guest_borrowing_mode", "hard_visit_cap"]}
    with pytest.raises(Exception):
        guest_pass_policy.update_policy(actor, makerspace, {"guest_borrowing_mode": "everything"})
    with pytest.raises(Exception):
        guest_pass_policy.update_policy(actor, makerspace, {"not_a_setting": 1})


def test_sponsored_pass_is_a_permit_not_a_membership_and_freezes_entitlements():
    makerspace = _space()
    sponsor, guest = _sponsor(makerspace), user("visitor")
    row, created = guest_pass_issue.issue_sponsored_pass(sponsor, makerspace, guest)
    assert created and row.kind == "sponsored" and row.sponsor_id == sponsor.pk
    assert not MakerspaceMembership.objects.filter(makerspace=makerspace, user=guest).exists()
    assert row.entitlements == {"presence": True, "borrow": "on_site", "machines": "none"}
    # A later policy change never rewrites the live pass.
    guest_pass_policy.update_policy(manager(makerspace), makerspace, {"guest_borrowing_mode": "none"})
    row.refresh_from_db()
    assert row.entitlements["borrow"] == "on_site"
    found = active_pass_for(guest, makerspace)
    assert found.pk == row.pk
    ent = pass_entitlements(found)
    assert ent.on_site_only and ent.due_by == row.valid_until and ent.machines == "none"
    assert AuditLog.objects.filter(makerspace=makerspace, action="membership.guest_pass_issued").count() == 1


def test_sponsor_checks_tenure_limit_and_one_pass_per_day():
    makerspace = _space()
    GuestPassPolicy.objects.filter(makerspace=makerspace).update(max_concurrent_guests_per_sponsor=1)
    fresh = _sponsor(makerspace, "fresh", days=2)
    with pytest.raises(GuestPassError) as refused:
        guest_pass_issue.issue_sponsored_pass(fresh, makerspace, user("g0"))
    assert refused.value.error_code == "sponsor_tenure"
    sponsor, first = _sponsor(makerspace), user("g1")
    guest_pass_issue.issue_sponsored_pass(sponsor, makerspace, first)
    with pytest.raises(GuestPassError) as refused:
        guest_pass_issue.issue_sponsored_pass(sponsor, makerspace, user("g2"))
    assert refused.value.error_code == "sponsor_limit"
    other = _sponsor(makerspace, "other")
    with pytest.raises(GuestPassError) as refused:
        guest_pass_issue.issue_sponsored_pass(other, makerspace, first)
    assert refused.value.error_code == "pass_exists_today"


def test_non_member_cannot_sponsor_and_a_member_needs_no_pass():
    makerspace = _space()
    with pytest.raises(GuestPassError) as refused:
        guest_pass_issue.issue_sponsored_pass(user("outsider"), makerspace, user("friend"))
    assert refused.value.error_code == "sponsor_not_member"
    sponsor, member = _sponsor(makerspace), _sponsor(makerspace, "already")
    with pytest.raises(GuestPassError) as refused:
        guest_pass_issue.issue_sponsored_pass(sponsor, makerspace, member)
    assert refused.value.error_code == "already_member"


def test_switch_off_stops_unlocking_and_blocks_new_passes():
    makerspace = _space()
    sponsor, guest = _sponsor(makerspace), user("visitor")
    guest_pass_issue.issue_sponsored_pass(sponsor, makerspace, guest)
    makerspace.enabled_features = [key for key in makerspace.enabled_features if key != "membership.guest_passes"]
    makerspace.save(update_fields=["enabled_features"])
    assert active_pass_for(guest, makerspace) is None
    assert GuestPass.objects.filter(makerspace=makerspace).count() == 1  # recorded, just inert
    with pytest.raises(Exception):
        guest_pass_issue.issue_sponsored_pass(sponsor, makerspace, user("late"))


def test_window_bounds_the_pass_and_restricted_holders_get_nothing():
    makerspace = _space()
    guest = user("visitor")
    row, _ = guest_pass_issue.issue_staff_pass(manager(makerspace), makerspace, guest)
    assert active_pass_for(guest, makerspace, at=row.valid_from - timedelta(minutes=1)) is None
    assert active_pass_for(guest, makerspace, at=row.valid_until) is None
    guest.access_status = "restricted"
    guest.save(update_fields=["access_status"])
    assert active_pass_for(guest, makerspace) is None


def test_event_pass_is_idempotent_for_a_holder_and_day():
    makerspace = _space()
    guest = user("attendee")
    start = timezone.now() + timedelta(hours=2)
    begin, end = guest_pass_issue.event_window(start, start + timedelta(hours=3), return_hours=2)
    first, created = guest_pass_issue.issue_event_pass(makerspace, guest, begin, end, operation_id="reg-1")
    again, created_again = guest_pass_issue.issue_event_pass(makerspace, guest, begin, end, operation_id="reg-1")
    assert created and not created_again and first.pk == again.pk and first.kind == "event"
    assert end - begin == timedelta(hours=1 + 3 + 2)


def test_waiver_gate_and_stamp_follow_the_current_version():
    from apps.presence.guard import WaiverAcceptanceRequired
    makerspace = _space()
    guest = user("visitor")
    row, _ = guest_pass_issue.issue_staff_pass(manager(makerspace), makerspace, guest)
    require_waiver(guest, makerspace, row)  # no waiver published: nothing to accept
    waiver = MakerspaceWaiver.objects.create(makerspace=makerspace, body="Be safe.", version="v1", is_active=True)
    with pytest.raises(WaiverAcceptanceRequired):
        require_waiver(guest, makerspace, row)
    row = guest_pass_lifecycle.stamp_waiver(guest, row)
    assert (row.accepted_waiver_id, row.waiver_version) == (waiver.pk, "v1")
    require_waiver(guest, makerspace, row)
    GuestPassPolicy.objects.filter(makerspace=makerspace).update(waiver_required_on_site=False)
    MakerspaceWaiver.objects.filter(pk=waiver.pk).update(is_active=False)
    MakerspaceWaiver.objects.create(makerspace=makerspace, body="New.", version="v2", is_active=True)
    require_waiver(guest, makerspace, row)  # space no longer requires one
    entry = AuditLog.objects.get(makerspace=makerspace, action="membership.guest_pass_waiver_stamped")
    assert "Be safe" not in str(entry.meta)


def test_waiver_triple_is_all_or_none():
    makerspace = _space()
    row, _ = guest_pass_issue.issue_staff_pass(manager(makerspace), makerspace, user("visitor"))
    with pytest.raises(IntegrityError), transaction.atomic():
        GuestPass.objects.filter(pk=row.pk).update(waiver_version="v1")


def test_revoke_frees_the_day_and_unlocks_nothing():
    makerspace = _space()
    guest = user("visitor")
    row, _ = guest_pass_issue.issue_staff_pass(manager(makerspace), makerspace, guest)
    guest_pass_lifecycle.revoke_pass(manager(makerspace, "m2"), row, "left early")
    row.refresh_from_db()
    assert row.status == "revoked" and row.revoked_reason == "left early"
    assert active_pass_for(guest, makerspace) is None
    with pytest.raises(GuestPassError):
        guest_pass_lifecycle.revoke_pass(manager(makerspace, "m3"), row)
    guest_pass_issue.issue_staff_pass(manager(makerspace, "m4"), makerspace, guest)  # the day slot is free again
    audit = AuditLog.objects.get(makerspace=makerspace, action="membership.guest_pass_revoked")
    assert "left early" not in str(audit.meta)


def test_expire_sweep_and_conversion_marker():
    makerspace = _space()
    guest = user("visitor")
    row, _ = guest_pass_issue.issue_staff_pass(manager(makerspace), makerspace, guest)
    assert guest_pass_lifecycle.expire_due_passes(makerspace, now=row.valid_until + timedelta(seconds=1)) == 1
    row.refresh_from_db()
    assert row.status == "expired"
    membership = MakerspaceMembership.objects.create(
        makerspace=makerspace, user=guest, assigned_role=member_role(makerspace), role="custom", status="active")
    assert guest_pass_lifecycle.mark_converted(membership) == 1
    row.refresh_from_db()
    assert row.status == "converted" and row.converted_membership_id == membership.pk


def test_visit_summary_prompts_join_after_n_visits_and_hard_cap_refuses():
    makerspace = _space()
    GuestPassPolicy.objects.filter(makerspace=makerspace).update(visits_before_join_prompt=2, hard_visit_cap=3)
    guest, staff = user("regular"), manager(makerspace)
    for offset in (3, 2, 1):
        start = timezone.now() - timedelta(days=offset)
        GuestPass.objects.create(
            makerspace=makerspace, holder=guest, kind="day", status="expired", valid_from=start,
            valid_until=start + timedelta(hours=8), pass_date=start.date(), entitlements={})
    summary = visit_summary(guest, makerspace)
    assert summary["visits_30d"] == 3 and summary["should_prompt_join"] and summary["hard_cap_reached"]
    with pytest.raises(GuestPassError) as refused:
        guest_pass_issue.issue_staff_pass(staff, makerspace, guest)
    assert refused.value.error_code == "visit_cap_reached"


def _product(makerspace, amount="12.00", **extra):
    return DayPassProduct.objects.create(makerspace=makerspace, name="Day", amount=Decimal(amount), currency="usd",
                                         **extra)


def test_priced_day_pass_records_the_debt_and_unlocks_only_once_settled():
    makerspace = _space("gp-paid", charges=True)
    staff, guest = manager(makerspace), user("buyer")
    row, payment = guest_pass_day.sell_day_pass(guest, makerspace, guest, _product(makerspace))
    assert payment.subject_type == Payment.SubjectType.GUEST_PASS and payment.subject_id == row.pk
    assert payment.status == Payment.Status.PENDING and payment.member_id == guest.pk
    assert active_pass_for(guest, makerspace) is None  # unpaid: nothing unlocks
    mark_offline(payment, staff, settlement=settlement_details())
    assert active_pass_for(guest, makerspace).pk == row.pk


def test_priced_product_needs_charges_on_and_a_free_one_is_usable_at_once():
    makerspace = _space("gp-free", charges=False)
    guest = user("buyer")
    with pytest.raises(GuestPassError) as refused:
        guest_pass_day.sell_day_pass(guest, makerspace, guest, _product(makerspace))
    assert refused.value.error_code == "charges_off"
    with pytest.raises(GuestPassError):
        guest_pass_day.save_product(manager(makerspace), makerspace, {"name": "Priced", "amount": Decimal("5")})
    free = _product(makerspace, "0.00", name="Free")
    row, payment = guest_pass_day.sell_day_pass(guest, makerspace, guest, free)
    assert payment is None and active_pass_for(guest, makerspace).pk == row.pk


def test_daily_cap_refuses_and_archived_product_is_not_sold():
    makerspace = _space("gp-cap", charges=False)
    product = _product(makerspace, "0.00", daily_cap=1)
    guest_pass_day.sell_day_pass(user("a"), makerspace, user("a2"), product)
    with pytest.raises(GuestPassError) as refused:
        guest_pass_day.sell_day_pass(user("b"), makerspace, user("b2"), product)
    assert refused.value.error_code == "day_pass_sold_out"
    guest_pass_day.archive_product(manager(makerspace), product)
    with pytest.raises(GuestPassError) as refused:
        guest_pass_day.sell_day_pass(user("c"), makerspace, user("c2"), product)
    assert refused.value.error_code == "product_unavailable"


def test_revoking_a_paid_day_pass_opens_a_refund_case():
    from apps.payments.models import RefundCase
    makerspace = _space("gp-refund", charges=True)
    staff, guest = manager(makerspace), user("buyer")
    row, payment = guest_pass_day.sell_day_pass(guest, makerspace, guest, _product(makerspace))
    mark_offline(payment, staff, settlement=settlement_details())
    guest_pass_lifecycle.revoke_pass(staff, row, "wrong day")
    assert RefundCase.objects.filter(makerspace=makerspace, payment=payment).exists()
    assert AuditLog.objects.get(makerspace=makerspace, action="membership.guest_pass_revoked").meta[
        "refund_opened"] is True
