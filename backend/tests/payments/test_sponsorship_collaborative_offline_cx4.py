"""Real charge seams with the rail removed: receipts, refunds, replay and audit."""
from decimal import Decimal
from unittest.mock import Mock

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.makerspaces.module_install import install_module, uninstall_module
from apps.payments.availability import online_payments_enabled
from apps.payments.resolution import resolve_payment_source
from apps.payments.donations.refunds import open_return_case
from apps.payments.exceptions_refunds import RefundCaseConflict, RefundNotAllowed
from apps.payments.models import ManualSettlement, Payment, Refund, RefundCase
from apps.payments.reconciliation import mark_offline
from apps.payments.services_refund_decisions import approve_case
from apps.payments.services_refunds_offline import record_offline_refund
from tests.payments.test_models import configured_settings
from tests.return_helpers import settlement_details

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def no_broker(monkeypatch):
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", lambda *_: None)
    monkeypatch.setattr("apps.integrations.dispatch_outbox._enqueue", lambda *_: None)


@pytest.fixture
def provider_checkout(monkeypatch):
    checkout = Mock(side_effect=AssertionError("A settled charge must not create a provider checkout"))
    monkeypatch.setattr("apps.payments.stripe_client.create_checkout_session", checkout)
    return checkout


def enable_rail(space, domain):
    install_module(space, "payments")
    # Module mutations refresh only enabled_modules; restore pruned features from a full read.
    space.refresh_from_db()
    space.enabled_features = sorted(set(space.enabled_features) | {"payments.enabled", f"payments.{domain}"})
    space.save(update_fields=["enabled_features"])
    space.refresh_from_db()
    source = resolve_payment_source(space)
    assert source is not None
    assert (source.vendor, source.provider) == ("stripe", "raw")
    assert online_payments_enabled(space, domain) is True


def remove_rail(space, domain):
    uninstall_module(space, "payments")
    space.refresh_from_db()
    assert resolve_payment_source(space) is not None  # credentials survive removal
    assert online_payments_enabled(space, domain) is False


def assert_no_checkout(payment, provider_checkout):
    payment.refresh_from_db()
    assert (payment.online_rail, payment.external_order_id, payment.external_payment_id, payment.checkout_url,
            payment.stripe_checkout_session_id, payment.stripe_checkout_url, payment.stripe_payment_intent_id) == (
                None, None, None, "", None, "", None)
    provider_checkout.assert_not_called()


def receipt(reference):
    return {"method": "cash", "reference": reference, "refunded_at": timezone.now()}


def audits(payment, action):
    return AuditLog.objects.filter(makerspace=payment.makerspace, target_id=str(payment.pk), action=action)


def settle_once(payment, manager):
    assert (payment.status, payment.provider, payment.online_rail) == ("pending", "unclaimed", None)
    assert audits(payment, "payment.created").count() == 1
    with pytest.raises(ValueError, match="^Marking a payment paid offline requires settlement details\\.$"):
        mark_offline(payment, manager, settlement=None)
    payment.refresh_from_db()
    assert payment.status == Payment.Status.PENDING
    assert ManualSettlement.objects.filter(payment=payment).count() == 0
    assert audits(payment, "payment.paid_offline").count() == 0
    mark_offline(payment, manager, settlement=settlement_details(reference="cx4-cash"))
    # The compatibility service is an idempotent no-op on a terminal row.
    mark_offline(payment, manager, settlement=settlement_details(reference="must-not-replace"))
    payment.refresh_from_db()
    assert payment.status == Payment.Status.PAID_OFFLINE
    [settlement] = ManualSettlement.objects.filter(payment=payment)
    assert (settlement.method, settlement.reference, settlement.amount, settlement.currency) == (
        "cash", "cx4-cash", payment.amount, payment.currency)
    assert audits(payment, "payment.paid_offline").count() == 1


def test_sponsorship_partial_then_full_refund_requires_two_staff_decisions(provider_checkout):
    from tests.l18_local.helpers import client, setup
    from tests.l18_local.test_sponsors import _sponsor, url

    space, manager, _ = setup("cx4-sponsor", "finance.sponsors")
    configured_settings(space)
    enable_rail(space, "donations")
    remove_rail(space, "donations")
    sponsor = _sponsor(space, manager)
    response = client(manager).post(url(space, f"/{sponsor.pk}/charges"),
                                    {"amount": "25000", "description": "Lab support"}, format="json")
    assert response.status_code == 201, response.content
    payment = Payment.objects.get(makerspace=space, subject_type="sponsorship", subject_id=response.json()["id"])
    assert (payment.member_id, payment.amount) == (None, Decimal("25000"))
    settle_once(payment, manager)
    case = open_return_case(payment, actor=manager, reason="Partial return")
    with pytest.raises(RefundNotAllowed) as missing:
        approve_case(case, actor=manager, amount="10000")
    assert (missing.value.status_code, missing.value.detail["code"]) == (400, "refund_receipt_required")
    case.refresh_from_db()
    assert case.status == RefundCase.Status.OPEN
    assert Refund.objects.filter(payment=payment).count() == 0
    approved = approve_case(case, actor=manager, amount="10000", receipt=receipt("partial"))
    assert (approved.status, approved.refund.amount) == (RefundCase.Status.APPROVED, Decimal("10000"))
    with pytest.raises(RefundCaseConflict) as replay:
        approve_case(case, actor=manager, amount="10000", receipt=receipt("replay"))
    assert (replay.value.status_code, replay.value.detail["code"]) == (409, "refund_case_closed")
    remainder = open_return_case(payment, actor=manager, reason="Return remainder")
    assert remainder.due_amount == Decimal("15000")
    with pytest.raises(RefundCaseConflict) as over:
        approve_case(remainder, actor=manager, amount="15000.01", receipt=receipt("too-much"))
    assert (over.value.status_code, over.value.detail["code"]) == (409, "refund_exceeds_balance")
    assert Refund.objects.filter(payment=payment).count() == 1
    approve_case(remainder, actor=manager, receipt=receipt("remainder"))
    assert list(Refund.objects.filter(payment=payment).order_by("pk").values_list("amount", "reference")) == [
        (Decimal("10000"), "partial"), (Decimal("15000"), "remainder")]
    assert Refund.counted_total(payment) == payment.amount
    assert audits(payment, "payment.refund_recorded").count() == 2
    assert AuditLog.objects.filter(makerspace=space, action="payment.refund_case_approved").count() == 2
    with pytest.raises(RefundNotAllowed) as exhausted:
        open_return_case(payment, actor=manager)
    assert (exhausted.value.status_code, exhausted.value.detail["code"]) == (400, "refund_exceeds_balance")
    assert ManualSettlement.objects.filter(payment=payment).count() == 1
    enable_rail(space, "donations")
    audit_before = list(AuditLog.objects.filter(makerspace=space, target_type="payments.payment",
                                               target_id=str(payment.pk)).order_by("pk").values())
    # Sponsor charge creation is deliberately not replayable; read and settle the existing charge instead.
    mark_offline(payment, manager, settlement=settlement_details(reference="restored-must-not-replace"))
    first = client(manager).get(url(space, f"/{sponsor.pk}/charges"))
    replay = client(manager).get(url(space, f"/{sponsor.pk}/charges"))
    assert first.status_code == 200, first.content
    assert replay.status_code == 200, replay.content
    assert replay.json() == first.json()
    assert [(row["id"], row["payment_id"], row["payment_status"]) for row in first.json()] == [
        (response.json()["id"], payment.pk, "paid_offline")]
    assert sponsor.charges.count() == 1
    assert Payment.objects.filter(makerspace=space, subject_type="sponsorship").count() == 1
    assert ManualSettlement.objects.filter(payment=payment).count() == 1
    assert ManualSettlement.objects.get(payment=payment).reference == "cx4-cash"
    assert Refund.objects.filter(payment=payment).count() == 2
    assert audits(payment, "payment.created").count() == 1
    assert audits(payment, "payment.paid_offline").count() == 1
    assert audits(payment, "payment.refund_recorded").count() == 2
    assert AuditLog.objects.filter(makerspace=space, action="payment.refund_case_approved").count() == 2
    assert list(AuditLog.objects.filter(makerspace=space, target_type="payments.payment",
                                       target_id=str(payment.pk)).order_by("pk").values()) == audit_before
    assert (payment.status, payment.provider) == (Payment.Status.PAID_OFFLINE, Payment.Provider.UNCLAIMED)
    assert_no_checkout(payment, provider_checkout)


def test_collaborative_event_host_charge_keeps_partner_routing_through_offline_refunds(
        provider_checkout, django_capture_on_commit_callbacks):
    from apps.events.models import EventRegistration
    from apps.events.service_payments import create_for_registered_registration
    from apps.payments.member_scope import member_payment_queryset
    from tests.events.collab_helpers import collaborate, make_event, make_member, make_space, make_staff

    host, partner = make_space("cx4-host"), make_space("cx4-partner")
    host.enabled_features = sorted(set(host.enabled_features) | {"charges.enabled", "charges.events"})
    host.save(update_fields=["enabled_features"])
    configured_settings(host)
    enable_rail(host, "events")
    remove_rail(host, "events")
    manager, visitor = make_staff(host), make_member(partner)
    event = make_event(host)
    event.payment_amount = Decimal("8.00")
    event.save(update_fields=["payment_amount"])
    collaborate(event, partner)
    registration = EventRegistration.objects.create(event=event, member=visitor, name=visitor.display_name,
        email=visitor.email, phone=visitor.phone, registered_via_makerspace=partner, payment_via_makerspace=partner)
    payment = create_for_registered_registration(registration, manager)
    assert payment is not None
    assert (payment.makerspace_id, payment.via_makerspace_id, payment.member_id, payment.amount) == (
        host.pk, partner.pk, visitor.pk, Decimal("8.00"))
    assert create_for_registered_registration(registration, manager).pk == payment.pk
    settle_once(payment, manager)
    record_offline_refund(payment, amount="3", reason="Partial", actor=manager, receipt=receipt("partial"))
    with pytest.raises(RefundNotAllowed) as over:
        record_offline_refund(payment, amount="5.01", reason="Too much", actor=manager, receipt=receipt("over"))
    assert (over.value.status_code, over.value.detail["code"]) == (400, "refund_exceeds_balance")
    record_offline_refund(payment, amount="5", reason="Remainder", actor=manager, receipt=receipt("remainder"))
    assert list(Refund.objects.filter(payment=payment).order_by("pk").values_list("amount", "reference")) == [
        (Decimal("3"), "partial"), (Decimal("5"), "remainder")]
    assert audits(payment, "payment.refund_recorded").count() == 2
    for space in (host, partner):
        uninstall_module(space, "event_reimbursements")
        uninstall_module(space, "events")
    assert list(member_payment_queryset(visitor, partner.pk).values_list("pk", flat=True)) == [payment.pk]
    assert EventRegistration.objects.filter(pk=registration.pk, status="registered").count() == 1
    for space in (host, partner):
        install_module(space, "events")
        install_module(space, "event_reimbursements")
    enable_rail(host, "events")
    audit_before = list(AuditLog.objects.filter(makerspace=host, target_type="payments.payment",
                                               target_id=str(payment.pk)).order_by("pk").values())
    with django_capture_on_commit_callbacks(execute=True):
        assert create_for_registered_registration(registration, manager).pk == payment.pk
    payment.refresh_from_db()
    assert (payment.status, payment.provider) == (Payment.Status.PAID_OFFLINE, Payment.Provider.UNCLAIMED)
    assert ManualSettlement.objects.filter(payment=payment).count() == 1
    assert Refund.objects.filter(payment=payment).count() == 2
    assert audits(payment, "payment.created").count() == 1
    assert Payment.objects.filter(makerspace=host, subject_type="event_registration").count() == 1
    assert audits(payment, "payment.paid_offline").count() == 1
    assert audits(payment, "payment.refund_recorded").count() == 2
    assert list(AuditLog.objects.filter(makerspace=host, target_type="payments.payment",
                                       target_id=str(payment.pk)).order_by("pk").values()) == audit_before
    assert_no_checkout(payment, provider_checkout)
