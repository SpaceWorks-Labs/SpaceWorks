"""Lane L15 (A1): loan rental at checkout (planned days) or at return (actual days)."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.payments.models import Payment, PricingDefault
from apps.payments.pricing.build_loans import days_between
from tests.hardware_requests.test_loan_payments import (  # noqa: F401 -- autouse fixture
    accepted_loan, close, issue, loan_payment, quiet_storage_and_stripe,
)
from tests.payments.pricing.helpers import D, pricing_space, rate, switch
from tests.return_helpers import make_member, make_product

pytestmark = pytest.mark.django_db


def space_with_rental(slug, timing="at_checkout", **settings):
    space, _ = pricing_space(slug, **settings)
    staff = make_member(f"{slug}-staff", space)
    row = rate(space, "loans", rental_per_loan="1.00", rental_per_day=("2.00", {"cap": D("9.00")}))
    row.rental_timing = timing
    row.save()
    return space, staff


def test_at_checkout_charges_the_planned_days_once(django_capture_on_commit_callbacks):
    space, staff = space_with_rental("rent-checkout")
    request = accepted_loan(space, staff, product=make_product(space), quantity=2)
    issue(staff, request, django_capture_on_commit_callbacks)
    request.refresh_from_db()
    days = days_between(request.issued_at, request.return_due_at)
    rental = loan_payment(request, Payment.SubjectType.LOAN_RENTAL)
    assert rental.amount == D("2.00") + min(D("2.00") * days, D("9.00")) * 2
    assert rental.pricing_snapshot["domain"] == "loans" and rental.pricing_snapshot["digest"]
    assert AuditLog.objects.get(action="loan.rental_raised").meta["timing"] == "checkout"
    close(staff, request, django_capture_on_commit_callbacks)  # an early return refunds nothing
    rental.refresh_from_db()
    assert rental.status == Payment.Status.PENDING
    assert Payment.objects.filter(subject_type="loan_rental", subject_id=request.pk).count() == 1


def test_at_return_charges_the_actual_days_and_the_late_fee_still_applies(django_capture_on_commit_callbacks):
    space, staff = space_with_rental("rent-return", "at_return", loan_late_fee_per_day=D("3.00"))
    request = accepted_loan(space, staff, product=make_product(space))
    issue(staff, request, django_capture_on_commit_callbacks)
    assert loan_payment(request, Payment.SubjectType.LOAN_RENTAL) is None
    assert AuditLog.objects.filter(action="loan.rental_deferred", target_id=str(request.pk)).exists()
    request.refresh_from_db()
    request.issued_at = timezone.now() - timedelta(days=6, hours=1)
    request.return_due_at = timezone.now() - timedelta(days=2) + timedelta(minutes=5)
    request.save(update_fields=["issued_at", "return_due_at"])
    close(staff, request, django_capture_on_commit_callbacks)
    rental = loan_payment(request, Payment.SubjectType.LOAN_RENTAL)
    assert rental.amount == D("1.00") + D("9.00")  # 7 days x 2.00 capped at 9.00 per unit
    assert loan_payment(request, Payment.SubjectType.LOAN_LATE_FEE).amount == D("6.00")


def test_a_timing_change_applies_only_to_loans_issued_after_it(django_capture_on_commit_callbacks):
    space, staff = space_with_rental("rent-change", "at_return")
    deferred = accepted_loan(space, staff, product=make_product(space, name="A"))
    issue(staff, deferred, django_capture_on_commit_callbacks)
    PricingDefault.objects.filter(makerspace=space, domain="loans").update(rental_timing="at_checkout")
    later = accepted_loan(space, staff, product=make_product(space, name="B"))
    issue(staff, later, django_capture_on_commit_callbacks)
    assert loan_payment(later, Payment.SubjectType.LOAN_RENTAL) is not None
    assert loan_payment(deferred, Payment.SubjectType.LOAN_RENTAL) is None
    deferred.refresh_from_db()
    close(staff, deferred, django_capture_on_commit_callbacks)
    assert loan_payment(deferred, Payment.SubjectType.LOAN_RENTAL).amount == D("3.00")  # 1 day + per loan


def test_free_default_and_pricing_off_raise_no_rental(django_capture_on_commit_callbacks):
    space, staff = space_with_rental("rent-free")
    PricingDefault.objects.filter(makerspace=space, domain="loans").update(mode="free")
    request = accepted_loan(space, staff, product=make_product(space))
    issue(staff, request, django_capture_on_commit_callbacks)
    assert loan_payment(request, Payment.SubjectType.LOAN_RENTAL) is None
    PricingDefault.objects.filter(makerspace=space, domain="loans").update(mode="paid")
    switch(space, "charges.pricing", on=False)
    second = accepted_loan(space, staff, product=make_product(space, name="Second"))
    issue(staff, second, django_capture_on_commit_callbacks)
    assert loan_payment(second, Payment.SubjectType.LOAN_RENTAL) is None
