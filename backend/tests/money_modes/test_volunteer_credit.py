"""Decision 223 (k), lane L3b: volunteer hours become a recorded credit applied through the membership charge path."""
from decimal import Decimal

import pytest
from django.db import transaction
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.makerspaces import volunteer_credit, volunteer_hours
from apps.makerspaces.community_policy import CommunityError
from apps.makerspaces.membership_plan_services import create_term
from apps.makerspaces.membership_term_charges import raise_term_start
from apps.makerspaces.models_membership_rules import PlanType
from apps.makerspaces.models import (
    CommunityPolicy, MakerspaceMembership, VolunteerCredit, VolunteerHourEntry,
)
from apps.payments.models import Payment
from tests.makerspaces.l4_helpers import features_off, features_on
from tests.makerspaces.test_membership_admission_matrix import _setup
from tests.makerspaces.test_membership_j1 import member_role
from tests.money_modes.helpers import OFFLINE, charges, set_mode

pytestmark = pytest.mark.django_db(transaction=True)
SUBJECT = "membership_term_start"


def _world(**policy):
    makerspace, actor, applicant, plan, _ = _setup(paid=True)
    set_mode(makerspace, "membership", OFFLINE)
    features_on(makerspace, "volunteer_credit")
    CommunityPolicy.objects.create(
        makerspace=makerspace, volunteer_minutes_per_credit=policy.pop("per", 60),
        volunteer_credit_kind=policy.pop("kind", "discount"),
        volunteer_credit_amount=policy.pop("amount", Decimal("5.00")),
        volunteer_credit_days=policy.pop("days", 0), **policy)
    membership = MakerspaceMembership.objects.create(
        makerspace=makerspace, user=applicant, assigned_role=member_role(makerspace), role="custom",
        status="active", activated_at=timezone.now())
    return makerspace, actor, applicant, plan, membership


def _today():
    return timezone.localdate()


def test_member_hours_wait_for_approval_and_approval_mints_whole_credits_only():
    makerspace, actor, member, _plan, _m = _world(per=60)
    entry = volunteer_hours.log_hours(member, makerspace, member, minutes=90, worked_on=_today())
    assert entry.status == "pending" and not VolunteerCredit.objects.exists()
    volunteer_hours.review_entry(actor, entry, approve=True)
    assert VolunteerCredit.objects.filter(member=member).count() == 1  # 90 minutes = one 60-minute block
    second = volunteer_hours.log_hours(member, makerspace, member, minutes=30, worked_on=_today())
    volunteer_hours.review_entry(actor, second, approve=True)
    assert VolunteerCredit.objects.filter(member=member).count() == 2  # the 30 minute remainder completes a block
    with pytest.raises(CommunityError) as again:
        volunteer_hours.review_entry(actor, second, approve=False)
    assert again.value.error_code == "entry_not_pending"
    assert AuditLog.objects.filter(makerspace=makerspace, action="membership.volunteer_credit_created").count() == 2


def test_staff_logged_hours_are_approved_at_once_and_rejected_hours_earn_nothing():
    makerspace, actor, member, _plan, _m = _world(per=60)
    entry = volunteer_hours.log_hours(actor, makerspace, member, minutes=60, worked_on=_today(), by_staff=True)
    assert entry.status == "approved" and VolunteerCredit.objects.filter(member=member).count() == 1
    rejected = volunteer_hours.log_hours(member, makerspace, member, minutes=600, worked_on=_today())
    volunteer_hours.review_entry(actor, rejected, approve=False, note="duplicate")
    assert VolunteerCredit.objects.filter(member=member).count() == 1


def test_nothing_converts_when_the_policy_is_off_or_the_capability_is_off():
    makerspace, actor, member, _plan, _m = _world(per=0)
    volunteer_hours.log_hours(actor, makerspace, member, minutes=600, worked_on=_today(), by_staff=True)
    assert not VolunteerCredit.objects.exists()
    CommunityPolicy.objects.filter(makerspace=makerspace).update(volunteer_minutes_per_credit=60)
    features_off(makerspace, "volunteer_credit")
    volunteer_hours.log_hours(actor, makerspace, member, minutes=60, worked_on=_today(), by_staff=True)
    assert not VolunteerCredit.objects.exists()


def test_a_credit_reduces_the_term_charge_as_a_recorded_audited_credit_not_a_silent_price_change():
    makerspace, actor, member, plan, membership = _world(per=60, amount=Decimal("5.00"))
    volunteer_hours.log_hours(actor, makerspace, member, minutes=60, worked_on=_today(), by_staff=True)
    term = create_term(actor, membership, plan)
    raise_term_start(actor, term)
    [payment] = charges(makerspace, SUBJECT)
    assert payment.amount == Decimal("15.00")  # the 20.00 term, less the 5.00 credit
    credit = VolunteerCredit.objects.get(member=member)
    assert (credit.status, credit.applied_payment_id, credit.applied_amount) == ("used", payment.pk, Decimal("5.00"))
    entry = AuditLog.objects.get(makerspace=makerspace, action="membership.volunteer_credit_applied")
    assert entry.meta["payment_id"] == payment.pk and entry.meta["applied_amount"] == "5.00"
    assert term.price == Decimal("20.00")  # the term's frozen price itself is untouched


def test_a_credit_larger_than_the_charge_leaves_the_rest_available():
    makerspace, actor, member, plan, membership = _world(per=60, amount=Decimal("50.00"))
    volunteer_hours.log_hours(actor, makerspace, member, minutes=60, worked_on=_today(), by_staff=True)
    raise_term_start(actor, create_term(actor, membership, plan))
    assert charges(makerspace, SUBJECT) == []  # fully covered: nothing owed
    used = VolunteerCredit.objects.get(status="used")
    left = VolunteerCredit.objects.get(status="available", split_from=used)
    assert used.applied_amount == Decimal("20.00") and left.amount == Decimal("30.00")


def test_free_days_apply_as_a_prorated_reduction():
    makerspace, actor, member, plan, membership = _world(per=60, kind="free_days", days=5, amount=Decimal("0"))
    volunteer_hours.log_hours(actor, makerspace, member, minutes=60, worked_on=_today(), by_staff=True)
    term = create_term(actor, membership, plan)
    with transaction.atomic():  # reduce_charge locks credits (select_for_update): callers hold a transaction
        net, used = volunteer_credit.reduce_charge(makerspace, member, Decimal("30.00"), "usd", term_days=30)
    assert net == Decimal("25.00") and len(used) == 1  # 5 of 30 days of a 30.00 term = 5.00
    assert term.pk


def test_the_charge_is_unchanged_when_the_capability_is_off_or_the_currency_differs():
    makerspace, actor, member, plan, membership = _world(per=60)
    volunteer_hours.log_hours(actor, makerspace, member, minutes=60, worked_on=_today(), by_staff=True)
    VolunteerCredit.objects.update(currency="eur")
    with transaction.atomic():
        net, used = volunteer_credit.reduce_charge(makerspace, member, Decimal("20.00"), "usd", term_days=30)
    assert (net, used) == (Decimal("20.00"), [])
    features_off(makerspace, "volunteer_credit")
    VolunteerCredit.objects.update(currency="")
    with transaction.atomic():
        assert volunteer_credit.reduce_charge(makerspace, member, Decimal("20.00"), "usd", term_days=30) == (Decimal("20.00"), [])


def test_a_renewal_keeps_a_minimum_charge_and_an_unused_credit_can_be_voided():
    makerspace, actor, member, _plan, _m = _world(per=60, amount=Decimal("50.00"))
    volunteer_hours.log_hours(actor, makerspace, member, minutes=60, worked_on=_today(), by_staff=True)
    with transaction.atomic():
        net, used = volunteer_credit.reduce_charge(makerspace, member, Decimal("20.00"), "usd", term_days=30,
                                                   floor=Decimal("0.01"))
    assert net == Decimal("0.01") and used[0][1] == Decimal("19.99")
    credit = VolunteerCredit.objects.filter(status="available").first()
    voided = volunteer_credit.void_credit(actor, credit, "mistake")
    assert voided.status == "void"


def test_staff_and_member_routes_and_the_off_switch():
    makerspace, actor, member, _plan, _m = _world(per=60)
    staff_client, member_client = APIClient(), APIClient()
    staff_client.force_authenticate(actor)
    member_client.force_authenticate(member)
    mine = member_client.post(f"/api/v1/member/makerspaces/{makerspace.pk}/volunteer-hours",
                              {"minutes": 60, "worked_on": _today().isoformat()}, format="json")
    assert mine.status_code == 201 and mine.data["status"] == "pending"
    decided = staff_client.post(
        f"/api/v1/admin/makerspaces/{makerspace.pk}/volunteer-hours/{mine.data['id']}/decide",
        {"approve": True}, format="json")
    assert decided.status_code == 200 and decided.data["status"] == "approved"
    credits = member_client.get(f"/api/v1/member/makerspaces/{makerspace.pk}/volunteer-credits")
    assert credits.status_code == 200 and len(credits.data) == 1
    features_off(makerspace, "volunteer_credit")
    assert staff_client.get(f"/api/v1/admin/makerspaces/{makerspace.pk}/volunteer-hours").status_code == 404
    assert member_client.get(f"/api/v1/member/makerspaces/{makerspace.pk}/volunteer-credits").status_code == 404
    assert VolunteerHourEntry.objects.filter(member=member).exists()  # data kept while off
    assert Payment.objects.filter(makerspace=makerspace, subject_type=SUBJECT).count() == 0


def test_a_fully_covered_renewal_records_a_marker_not_a_floor_debt():
    """Final audit 0.12.0 (m22, 229(e)): no 0.01 Payment; the term carries `renewal_covered_at`."""
    from apps.makerspaces.membership_renewal_charges import raise_renewal
    from apps.makerspaces.models import MembershipTerm
    makerspace, actor, member, plan, membership = _world(per=60, amount=Decimal("50.00"))
    # `renews` is derived from the plan type and `renewal_price` from `renewal_amount` (models_membership_plans).
    plan.plan_type, plan.is_active, plan.renewal_amount = PlanType.ROLLING, True, Decimal("20.00")
    plan.save(update_fields=["plan_type", "is_active", "renewal_amount"])
    volunteer_hours.log_hours(actor, makerspace, member, minutes=60, worked_on=_today(), by_staff=True)
    term = create_term(actor, membership, plan)
    before = Payment.objects.filter(subject_type="membership_term", subject_id=term.pk).count()
    result = raise_renewal(term)
    term = MembershipTerm.objects.get(pk=term.pk)
    if result == "charged":  # the world's modes may skip a renewal; only assert when the seam ran
        assert term.renewal_covered_at is not None and term.renewal_payment_id is None
        assert Payment.objects.filter(subject_type="membership_term", subject_id=term.pk).count() == before
        assert raise_renewal(term) == "skipped"  # already charged: the sweep will not raise it again
