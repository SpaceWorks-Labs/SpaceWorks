"""Every subject converges on one debt hook; bill failures roll back only a savepoint."""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.db import transaction
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.hardware_requests.models import HardwareRequest
from apps.makerspaces.models import MembershipRequest, MembershipTerm
from apps.payments.bill_sweeper import issue_missing_bills
from apps.payments.models import Payment, MakerspaceBillingSettings
from apps.payments.services import create_payment
from tests.makerspaces.test_membership_plans import plan
from tests.payments.test_machine_payments import service_request
from tests.payments.test_new_subjects import subjects
from tests.return_helpers import make_space, make_member

pytestmark = pytest.mark.django_db


def additional_subject(rows, subject_type, space, payer, actor):
    """Use real subjects so the charge hook also exercises Payment.clean() ownership checks."""
    from apps.events.models import (
        EventOrder, EventVenueFee, HackathonApplication, HackathonSubmission,
        HackathonTeam, HackathonTeamMember,
    )
    from apps.machines.models import MachineSession
    from apps.makerspaces.models import GuestPass
    from apps.payments.models import Donation, Sponsor, SponsorshipCharge
    from apps.shop.models import ShopOrder

    registration = rows["event_registration"]
    event = registration.event
    if subject_type == "machine_session":
        job = rows["machine_service_request"]
        machine = job.assigned_machine
        return MachineSession.objects.create(
            makerspace=space, machine=machine, machine_type=machine.machine_type,
            member=payer, source="member_qr", started_at=timezone.now())
    if subject_type == "event_order":
        return EventOrder.objects.create(makerspace=space, event=event, buyer=payer, currency="usd")
    if subject_type == "event_venue_fee":
        return EventVenueFee.objects.create(makerspace=space, event=event, payer=payer)
    if subject_type == "donation":
        return Donation.objects.create(makerspace=space, donor=payer, created_by=actor,
                                       amount="10.00", currency="usd")
    if subject_type == "sponsorship":
        sponsor = Sponsor.objects.create(makerspace=space, name="Bill hook sponsor", created_by=actor)
        return SponsorshipCharge.objects.create(makerspace=space, sponsor=sponsor, created_by=actor,
                                                amount="10.00", currency="usd")
    if subject_type in {"submission_fee", "team_registration"}:
        application = HackathonApplication.objects.create(
            event=event, member=payer, registration=registration, state="confirmed")
        team = HackathonTeam.objects.create(event=event, leader=payer, name="Bill hook team",
                                            normalized_name="bill hook team")
        # The deferred leader guard requires an active roster before this team is charged.
        HackathonTeamMember.objects.create(event=event, team=team, application=application,
            member=payer, state="active", creator=actor, joined_at=timezone.now())
        return HackathonSubmission.objects.create(event=event, team=team) if subject_type == "submission_fee" else team
    if subject_type == "event_deposit":
        return registration
    if subject_type == "shop_order":
        return ShopOrder.objects.create(makerspace=space, buyer=payer, currency="usd", pickup_code="BILL-HOOK")
    if subject_type == "membership_term_start":
        return rows["membership_term"]
    if subject_type == "guest_pass":
        now = timezone.now()
        return GuestPass.objects.create(makerspace=space, holder=payer, kind="day", issued_by=actor,
            valid_from=now, valid_until=now + timedelta(hours=8), pass_date=timezone.localdate(now))
    raise AssertionError(f"Missing bill-hook subject fixture: {subject_type}")


def charge_inputs(subject_type, slug="r1-hook"):
    space = make_space(slug)
    actor = make_member(slug + "-staff", space)
    payer = make_member(slug + "-payer", space, membership_role="custom", role="requester")
    rows = subjects(space, payer)
    rows["machine_service_request"] = service_request(space, payer)
    loan = HardwareRequest.objects.create(makerspace=space, requester=payer, requester_username=payer.username)
    rows.update(loan_deposit=loan, loan_late_fee=loan, loan_rental=loan)
    from apps.hardware_requests.models import RequesterAccountability
    for kind, issue in (("loan_damage", "damaged"), ("loan_lost", "missing")):
        rows[kind] = RequesterAccountability.objects.create(requester=payer, request=loan, makerspace=space,
                                                            issue_type=issue, quantity=1, created_by=actor)
    rows["membership_request"] = MembershipRequest.objects.create(
        makerspace=space, user=payer, kind="request", state="awaiting_payment")
    rows["membership_term"] = MembershipTerm.objects.create(
        membership=rows["makerspace_membership"], plan=plan(space), starts_at=timezone.now(),
        ends_at=timezone.now() + timedelta(days=30))
    row = rows.get(subject_type)
    if row is None:
        row = additional_subject(rows, subject_type, space, payer, actor)
    return dict(makerspace=space, member=None if subject_type == "sponsorship" else payer,
                created_by=actor, subject_type=subject_type, subject_id=row.pk,
                amount=Decimal("10.00"), currency="usd")


@pytest.mark.parametrize("subject_type", Payment.SubjectType.values)
@pytest.mark.parametrize("rail_on", [False, True])
def test_all_subjects_issue_bill_at_the_canonical_charge_boundary(subject_type, rail_on):
    from apps.payments.availability import SUBJECT_DOMAINS, online_payments_enabled
    from tests.payments.test_models import configured_settings
    from tests.return_helpers import enable_online_rail

    values = charge_inputs(subject_type)
    space = values["makerspace"]
    configured_settings(space)
    if rail_on:
        space.enabled_modules = sorted(set(space.enabled_modules) | {"payments"})
        if SUBJECT_DOMAINS[subject_type] == "donations":
            # payments.donations also requires the opt-in donation capability.
            space.enabled_features = sorted(set(space.enabled_features) | {"finance.donations"})
        space.save(update_fields=["enabled_modules", "enabled_features"])
        enable_online_rail(space, SUBJECT_DOMAINS[subject_type])
    else:
        space.enabled_modules = [key for key in space.enabled_modules if key != "payments"]
        space.save(update_fields=["enabled_modules"])
    assert online_payments_enabled(space, SUBJECT_DOMAINS[subject_type]) is rail_on
    payment = create_payment(**values)
    assert payment.provider == (Payment.Provider.STRIPE if rail_on else Payment.Provider.UNCLAIMED)
    assert payment.status == Payment.Status.PENDING
    bill = payment.documents.get(kind="bill")
    assert bill.amount == payment.amount == Decimal("10.00")
    assert bill.currency == "usd"
    assert bill.payer_label == (values["member"].username if values["member"] else "Account-less payer")
    assert AuditLog.objects.filter(makerspace=values["makerspace"], action="payment.document_issued",
                                   meta__kind="bill").count() == 1


def test_database_failure_in_optional_bill_does_not_poison_mandatory_outer_transaction(monkeypatch):
    values = charge_inputs("booking", "r1-savepoint")
    from apps.payments.documents import issue_bill as real_issue_bill
    def break_bill(payment, **kwargs):
        real_issue_bill(payment, **kwargs)
        # A real failed SQL statement after document writes, rather than a harmless Python exception.
        with transaction.get_connection().cursor() as cursor:
            cursor.execute("SELECT 1 / 0")
    monkeypatch.setattr("apps.payments.documents.issue_bill", break_bill)
    with transaction.atomic():
        payment = create_payment(**values)
        assert Payment.objects.filter(pk=payment.pk).exists()  # transaction still usable
        assert AuditLog.objects.filter(action="payment.created", target_id=str(payment.pk)).exists()
    assert not payment.documents.exists()
    assert not MakerspaceBillingSettings.objects.filter(makerspace=payment.makerspace).exists()
    assert not AuditLog.objects.filter(makerspace=payment.makerspace, action="payment.document_issued").exists()


def test_sweeper_recovers_a_failed_bill_once_and_command_uses_the_same_service(monkeypatch):
    from django.core.management import call_command
    values = charge_inputs("membership_term", "r1-recover")
    with patch("apps.payments.documents.issue_bill", side_effect=RuntimeError("temporary failure")):
        payment = create_payment(**values)
    first = issue_missing_bills(makerspace_id=payment.makerspace_id)
    assert first["issued"] == 1 and first["failed"] == 0
    assert issue_missing_bills(makerspace_id=payment.makerspace_id)["issued"] == 0
    call_command("issue_missing_bills", makerspace_id=payment.makerspace_id)
    assert payment.documents.filter(kind="bill").count() == 1


def test_sweeper_does_not_issue_into_a_frozen_tenant():
    values = charge_inputs("loan_deposit", "r1-frozen")
    with patch("apps.payments.documents.issue_bill", return_value=None):
        payment = create_payment(**values)
    # Exercise the real boundary without fabricating the gate's custody constraints.
    from apps.tenant_migration.gate_errors import SourceMigrationGateClosed
    with patch("apps.tenant_migration.gate_runtime.assert_write_allowed",
               side_effect=SourceMigrationGateClosed("Frozen", purpose="tenant_exit")):
        counts = issue_missing_bills(makerspace_id=payment.makerspace_id)
    assert counts["skipped"] == 1 and counts["issued"] == 0
    assert not payment.documents.exists()


def test_receipt_creation_remains_distinct_after_a_bill_and_no_rail_is_needed():
    from apps.payments.reconciliation import mark_offline
    from tests.return_helpers import settlement_details
    values = charge_inputs("membership_request", "r1-offline-bill")
    values["makerspace"].enabled_modules = []
    values["makerspace"].save(update_fields=["enabled_modules"])
    payment = create_payment(**values)
    assert payment.provider == "unclaimed"
    mark_offline(payment, values["created_by"], settlement_details())
    assert set(payment.documents.values_list("kind", flat=True)) == {"receipt", "bill"}


def test_bill_capability_restores_without_losing_or_duplicating_the_charge():
    from apps.payments.documents import issue_bill

    values = charge_inputs("booking", "r1-bill-toggle")
    space = values["makerspace"]
    features = space.enabled_features
    space.enabled_features = [key for key in features if key != "billing.documents"]
    space.save(update_fields=["enabled_features"])
    payment = create_payment(**values)
    assert payment.status == Payment.Status.PENDING
    assert not payment.documents.exists()
    assert issue_missing_bills(makerspace_id=space.pk) == {"issued": 0, "skipped": 0, "failed": 0}
    assert not AuditLog.objects.filter(makerspace=space, action="payment.document_issued").exists()

    space.enabled_features = sorted(set(features) | {"billing.documents"})
    space.save(update_fields=["enabled_features"])
    bill = issue_bill(payment)
    assert bill.amount == Decimal("10.00")
    assert issue_bill(payment).pk == bill.pk
    assert payment.documents.filter(kind="bill").count() == 1
    assert Payment.objects.filter(makerspace=space).count() == 1
    assert AuditLog.objects.filter(makerspace=space, action="payment.document_issued").count() == 1
