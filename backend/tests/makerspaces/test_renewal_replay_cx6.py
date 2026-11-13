"""Renewal seam: ledger-only work, module restoration and cancellation replays."""
from datetime import timedelta
from decimal import Decimal

import pytest
from rest_framework.exceptions import ValidationError

from apps.audit.models import AuditLog
from apps.makerspaces.membership_plan_services import cancel_term, create_term, run_membership_renewals
from apps.makerspaces.models import Makerspace, MembershipPlan, MembershipTerm
from apps.payments.models import Payment
from tests.accounts.account_factories import make_membership, make_staff
from tests.accounts.ua1_helpers import person

pytestmark = pytest.mark.django_db


@pytest.fixture
def renewal():
    from django.utils import timezone

    space = Makerspace.objects.create(name="Renewal replay", slug="cx6-renewal-replay",
        enabled_modules=["membership", "member_accounts"],
        enabled_features=["charges.enabled", "charges.membership", "membership.auto_renew"])
    actor = make_staff(space, username="cx6-renewal-manager")
    membership = make_membership(person("cx6-renewal-member"), space)
    plan = MembershipPlan.objects.create(makerspace=space, name="Renewable", interval="custom_days",
        custom_days=30, amount=Decimal("12.50"), currency="usd", auto_renew=True, renewal_open_days=7)
    term = create_term(actor, membership, plan, starts_at=timezone.now() - timedelta(days=26))
    return space, actor, membership, plan, term


def test_module_off_and_back_on_preserves_the_term_and_raises_exactly_one_unclaimed_debt(renewal):
    space, _, _, _, term = renewal
    now = term.ends_at - timedelta(days=1)
    space.enabled_modules = ["member_accounts"]
    space.save(update_fields=["enabled_modules"])
    result = run_membership_renewals(now=now)
    assert (result["charged"], result["opened"]) == (0, 0)
    assert Payment.objects.filter(subject_type="membership_term", subject_id=term.pk).count() == 0
    term.refresh_from_db()
    assert (term.status, term.renewal_payment_id) == ("active", None)
    space.enabled_modules = ["membership", "member_accounts"]
    space.save(update_fields=["enabled_modules"])
    assert run_membership_renewals(now=now)["charged"] == 1
    assert run_membership_renewals(now=now)["charged"] == 0
    payment = Payment.objects.get(subject_type="membership_term", subject_id=term.pk)
    assert (payment.amount, payment.currency, payment.provider, payment.status) == (
        Decimal("12.50"), "usd", "unclaimed", "pending")
    assert payment.member_id == term.membership.user_id
    assert AuditLog.objects.filter(action="membership.renewal_raised", target_id=str(term.pk)).count() == 1


@pytest.mark.parametrize("feature", ["charges.enabled", "charges.membership"])
def test_disabled_charge_capability_extends_once_without_a_payment(renewal, feature):
    space, _, membership, _, term = renewal
    space.enabled_features.remove(feature)
    space.save(update_fields=["enabled_features"])
    now = term.ends_at - timedelta(days=1)
    assert run_membership_renewals(now=now)["opened"] == 1
    assert run_membership_renewals(now=now)["opened"] == 0
    successor = MembershipTerm.objects.get(renewed_from=term)
    assert (successor.membership_id, successor.starts_at, successor.price) == (membership.pk, term.ends_at, Decimal("12.50"))
    assert Payment.objects.filter(subject_type="membership_term", subject_id=term.pk).count() == 0
    assert AuditLog.objects.filter(action="membership.renewed", target_id=str(term.pk)).count() == 1


def test_cancelling_a_term_voids_its_pending_renewal_and_replay_is_refused(renewal):
    _, actor, _, _, term = renewal
    assert run_membership_renewals(now=term.ends_at - timedelta(days=1))["charged"] == 1
    term.refresh_from_db()
    payment = term.renewal_payment
    cancelled = cancel_term(actor, term, reason="No longer needed", hold_charges=False)
    assert cancelled.status == MembershipTerm.Status.CANCELLED
    payment.refresh_from_db()
    assert payment.status == Payment.Status.CANCELED
    with pytest.raises(ValidationError) as error:
        cancel_term(actor, term, hold_charges=False)
    assert error.value.status_code == 400
    assert error.value.get_codes() == {"detail": "invalid"}
    assert str(error.value.detail["detail"]) == "This term is not active."
    assert AuditLog.objects.filter(action="membership.term_cancelled", target_id=str(term.pk)).count() == 1
