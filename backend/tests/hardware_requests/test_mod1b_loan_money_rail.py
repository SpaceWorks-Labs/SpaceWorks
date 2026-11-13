"""MOD-1B: money on loans with the online payment rail ON and OFF, and with charges off.

The ledger rule (CLAUDE.md Hard Rules): a loan debt is RECORDED whenever charge tracking is on, with or without
the payments rail; the rail only adds a checkout on top. So for deposit, rental, late fee and damage/lost charge:

* rail OFF (payments module not installed, credentials may still be saved): the row is `pending`, provider
  `unclaimed`, has no checkout url and no checkout is requested; staff settle it with a ManualSettlement receipt.
* rail ON: the row is stamped `stripe` and exactly one checkout is requested for it, after commit.
* charges OFF (`charges.enabled` or `charges.loans`): nothing is recorded, no audit row, issue and return still work.
"""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.boxes.models import QrCode
from apps.hardware_requests import loan_charges_common, loan_payments, workflow
from apps.hardware_requests.models import HardwareRequest, PublicToolLoan, RequesterAccountability
from apps.payments.models import MakerspacePaymentSettings, ManualSettlement, Payment
from tests.fixed_roles.helpers import staff_account
from tests.hardware_requests.test_loan_damage_lost import damaged_return, url as charge_url
from tests.hardware_requests.test_loan_payments import quiet_storage_and_stripe  # noqa: F401
from tests.payments.pricing.helpers import D, client, pricing_space, rate
from tests.return_helpers import (
    authenticated_client,
    make_issue_evidence,
    make_issued_request,
    make_member,
    make_product,
    make_return_evidence,
    settlement_payload,
)
from tests.test_public_self_checkout import eligible_member

pytestmark = pytest.mark.django_db


@pytest.fixture
def checkout(monkeypatch):
    mock = Mock()
    monkeypatch.setattr(loan_charges_common, "create_checkout", mock)
    return mock


def loans_space(slug, rail, **settings):
    """Charge tracking on for loans; the online rail on (module + credentials + features) or off (no module)."""
    space, manager = pricing_space(slug, "payments.enabled", "payments.loans", **settings)
    row = MakerspacePaymentSettings.for_makerspace(space)  # credentials saved in BOTH cases: module-off alone leaves the debt unclaimed
    row.set_stripe_secret_key("sk_test_secret")
    row.set_stripe_webhook_secret("whsec_test_secret")
    row.save()
    modules = set(space.enabled_modules or [])
    space.enabled_modules = sorted(modules | {"payments"} if rail else modules - {"payments"})
    space.save(update_fields=["enabled_modules", "updated_at"])
    return space, manager


def one(space, subject_type, subject_id):
    return Payment.objects.get(makerspace=space, subject_type=subject_type, subject_id=subject_id)


def overdue_return(space, staff, callbacks, days=10):
    request = make_issued_request(space, staff, [(make_product(space), 1)])
    request.return_due_at = timezone.now() - timedelta(days=days)
    request.save(update_fields=["return_due_at"])
    item = request.items.get()
    with callbacks(execute=True):
        workflow.return_items(staff, request, make_return_evidence(space, staff).pk, "Counted.", request.assigned_box.code,
                              [{"item_id": item.pk, "returned": 1, "damaged": 0, "missing": 0}])
    return request


LOAN_SETTINGS = dict(loan_deposit_mode="fixed", loan_deposit_amount=D("5.00"), loan_late_fee_per_day=D("2.00"),
                     loan_late_fee_cap=D("15.00"), loan_grace_days=1)


@pytest.mark.parametrize("rail", [False, True], ids=["rail_off", "rail_on"])
def test_each_loan_charge_follows_the_rail_switch_exactly(rail, checkout, django_capture_on_commit_callbacks):
    """Deposit, rental, late fee and damage: unclaimed + no checkout with the rail off; stripe + one checkout on."""
    space, staff = loans_space(f"mod1b-rail-{rail}", rail, **LOAN_SETTINGS)
    rate(space, "loans", rental_per_loan="3.00", damage="4.00")
    expected = "stripe" if rail else "unclaimed"

    issued = make_issued_request(space, staff, [(make_product(space), 1)])
    with django_capture_on_commit_callbacks(execute=True):
        loan_payments.on_request_issued(issued.pk, staff)
    deposit = one(space, "loan_deposit", issued.pk)
    rental = one(space, "loan_rental", issued.pk)
    assert [(p.status, p.provider, p.amount) for p in (deposit, rental)] == [
        (Payment.Status.PENDING, expected, D("5.00")), (Payment.Status.PENDING, expected, D("3.00"))]
    assert AuditLog.objects.filter(action="loan.deposit_raised", target_id=str(issued.pk)).count() == 1
    assert checkout.call_count == (2 if rail else 0)

    request = overdue_return(space, staff, django_capture_on_commit_callbacks)
    fee = one(space, "loan_late_fee", request.pk)
    assert (fee.status, fee.provider, fee.amount) == (Payment.Status.PENDING, expected, D("15.00"))
    assert AuditLog.objects.filter(action="loan.late_fee_raised", target_id=str(request.pk)).count() == 1
    assert checkout.call_count == (3 if rail else 0)

    manager = staff_account(space, f"mod1b-dmg-{rail}", "space_manager")
    damaged = damaged_return(space, manager, make_product(space), callbacks=django_capture_on_commit_callbacks)
    row = RequesterAccountability.objects.get(request=damaged)
    with django_capture_on_commit_callbacks(execute=True):
        reply = client(manager).post(charge_url(space, damaged, row), {"amount": "4.00"}, format="json")
    assert reply.status_code == 200, reply.data
    damage = one(space, "loan_damage", row.pk)
    assert (damage.status, damage.provider, damage.amount) == (Payment.Status.PENDING, expected, D("4.00"))
    assert AuditLog.objects.filter(action="loan.damage_charged", meta__accountability_id=row.pk).count() == 1
    assert checkout.call_count == (4 if rail else 0)
    if rail:
        assert [c.args[0].pk for c in checkout.call_args_list] == [deposit.pk, rental.pk, fee.pk, damage.pk]
    else:
        assert not any(p.checkout_url for p in Payment.objects.filter(makerspace=space))


def test_rail_off_loan_money_is_settled_offline_only_with_a_receipt(django_capture_on_commit_callbacks):
    space, staff = loans_space("mod1b-settle", False, **LOAN_SETTINGS)
    rate(space, "loans", damage="4.00")
    admin = staff_account(space, "mod1b-settle-admin", "space_manager")
    request = overdue_return(space, staff, django_capture_on_commit_callbacks)
    fee = one(space, "loan_late_fee", request.pk)
    base = f"/api/v1/admin/makerspace/{space.pk}/payments/{fee.pk}/mark-offline"

    bare = client(admin).post(base, {}, format="json")
    assert bare.status_code == 400
    fee.refresh_from_db()
    assert fee.status == Payment.Status.PENDING and not ManualSettlement.objects.filter(payment=fee).exists()

    settled = client(admin).post(base, settlement_payload(method="cash", reference="slip-77"), format="json")
    assert settled.status_code == 200, settled.data
    fee.refresh_from_db()
    receipt = ManualSettlement.objects.get(payment=fee)
    assert fee.status == Payment.Status.PAID_OFFLINE
    assert (receipt.method, receipt.reference, receipt.amount, receipt.currency) == ("cash", "slip-77", D("15.00"), fee.currency)
    assert AuditLog.objects.filter(action="payment.paid_offline", target_id=str(fee.pk)).count() == 1

    # A replay is refused and adds no second receipt or audit row.
    again = client(admin).post(base, settlement_payload(reference="slip-78"), format="json")
    assert again.status_code in (400, 409), again.data
    assert ManualSettlement.objects.filter(payment=fee).count() == 1
    assert AuditLog.objects.filter(action="payment.paid_offline", target_id=str(fee.pk)).count() == 1


@pytest.mark.parametrize("disabled", ["charges.enabled", "charges.loans"])
def test_charges_off_records_no_loan_money_and_never_blocks_the_handover(disabled, checkout, django_capture_on_commit_callbacks):
    space, staff = loans_space(f"mod1b-off-{disabled}", True, loan_deposit_blocks_issue=True, **LOAN_SETTINGS)
    rate(space, "loans", rental_per_loan="3.00", damage="4.00")
    space.enabled_features = [f for f in space.enabled_features if f != disabled]
    space.save(update_fields=["enabled_features", "updated_at"])

    issued = make_issued_request(space, staff, [(make_product(space), 1)])
    with django_capture_on_commit_callbacks(execute=True):
        assert loan_payments.on_request_issued(issued.pk, staff) is None
    assert not Payment.objects.filter(makerspace=space).exists()
    assert loan_payments.require_deposit_settled(issued, staff) is None  # a blocking deposit blocks nothing when untracked
    overdue_return(space, staff, django_capture_on_commit_callbacks)

    manager = staff_account(space, f"mod1b-off-m-{disabled}", "space_manager")
    damaged = damaged_return(space, manager, make_product(space), callbacks=django_capture_on_commit_callbacks)
    row = RequesterAccountability.objects.get(request=damaged)
    refused = client(manager).post(charge_url(space, damaged, row), {"amount": "4.00"}, format="json")
    assert refused.status_code == 404 and refused.data["code"] == "charges_off"
    assert not Payment.objects.filter(makerspace=space).exists()
    assert not AuditLog.objects.filter(makerspace=space, action__regex=r"^loan\.(deposit_raised|late_fee_raised|damage_charged)$").exists()
    assert checkout.call_count == 0


@pytest.mark.parametrize("cfg", [
    dict(loan_deposit_mode="fixed", loan_deposit_amount=D("0.00")),
    dict(loan_deposit_mode="fixed", loan_deposit_amount=D("0")),
], ids=["zero_2dp", "zero"])
def test_a_zero_deposit_and_a_zero_late_fee_raise_nothing(cfg, checkout, django_capture_on_commit_callbacks):
    space, staff = loans_space("mod1b-zero-" + str(cfg["loan_deposit_amount"]).replace(".", "p"), True, loan_late_fee_per_day=D("0.00"),
                               loan_deposit_blocks_issue=True, **cfg)
    issued = make_issued_request(space, staff, [(make_product(space), 1)])
    with django_capture_on_commit_callbacks(execute=True):
        assert loan_payments.on_request_issued(issued.pk, staff) is None
    assert loan_payments.require_deposit_settled(issued, staff) is None
    overdue_return(space, staff, django_capture_on_commit_callbacks)
    assert not Payment.objects.filter(makerspace=space).exists()
    assert checkout.call_count == 0


def test_a_late_fee_is_not_raised_exactly_at_the_end_of_grace_and_is_raised_one_day_later(
        checkout, monkeypatch, django_capture_on_commit_callbacks):
    space, staff = loans_space("mod1b-grace-edge", False, **LOAN_SETTINGS)
    now = timezone.now()
    monkeypatch.setattr(timezone, "now", lambda: now)
    edge = overdue_return(space, staff, django_capture_on_commit_callbacks, days=1)  # due exactly grace ago
    assert not Payment.objects.filter(makerspace=space, subject_type="loan_late_fee", subject_id=edge.pk).exists()
    over = overdue_return(space, staff, django_capture_on_commit_callbacks, days=2)
    assert one(space, "loan_late_fee", over.pk).amount == D("2.00")


@pytest.mark.parametrize("rail", [False, True], ids=["rail_off", "rail_on"])
def test_a_direct_handout_charges_the_borrower_with_or_without_the_rail(rail, checkout, django_capture_on_commit_callbacks):
    space, staff = loans_space(f"mod1b-direct-{rail}", rail, loan_deposit_mode="fixed", loan_deposit_amount=D("5.00"))
    rate(space, "loans", rental_per_loan="3.00")
    borrower = eligible_member(space, username=f"mod1b-direct-b-{rail}")
    product = make_product(space, public_self_checkout_enabled=True)
    qr = QrCode.objects.create(makerspace=space, target_type=QrCode.TargetType.PRODUCT, target_id=product.pk)
    evidence = make_issue_evidence(space, staff)
    with django_capture_on_commit_callbacks(execute=True):
        reply = authenticated_client(staff).post(
            f"/api/v1/admin/makerspace/{space.pk}/direct-loans",
            {"borrower_id": borrower.pk, "qr_payloads": [qr.payload], "evidence_id": evidence.pk}, format="json")
    assert reply.status_code == 201, reply.data
    loan = PublicToolLoan.objects.get(makerspace=space)
    request = loan.request
    assert request.status == HardwareRequest.Status.ISSUED
    expected = "stripe" if rail else "unclaimed"
    rows = {p.subject_type: p for p in Payment.objects.filter(makerspace=space, subject_id=request.pk)}
    assert set(rows) == {"loan_deposit", "loan_rental"}
    assert [(rows[k].status, rows[k].provider, rows[k].amount, rows[k].member_id) for k in ("loan_deposit", "loan_rental")] == [
        (Payment.Status.PENDING, expected, D("5.00"), borrower.pk), (Payment.Status.PENDING, expected, D("3.00"), borrower.pk)]
    assert checkout.call_count == (2 if rail else 0)
    assert AuditLog.objects.filter(action="loan.deposit_raised", target_id=str(request.pk)).count() == 1
