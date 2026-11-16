"""Archived accounts cannot acquire new work through staff or stale instances."""

from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.db import transaction
from django.utils import timezone

from apps.accounts.account_obligations import AccountDeletionPending, lock_obligation_owner
from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.bookings import services as bookings
from apps.events import services as events
from apps.events.models import EventRegistration
from apps.hardware_requests.loan_payments import on_request_closed
from apps.hardware_requests.models import HardwareRequest
from apps.hardware_requests.self_checkout_issue import checkout_tool
from apps.machines.service_workflow import submit
from apps.makerspaces.membership_plan_services import create_term
from apps.makerspaces.membership_renewal_charges import raise_renewal
from apps.makerspaces.models import MembershipPlan, MembershipTerm
from apps.payments.models import Payment
from tests.bookings.test_staff_tools_helpers import reserve, snapshot, world
from tests.events.test_lane_b_restore import setup_restore
from tests.hardware_requests.test_loan_payments import loan_space
from tests.makerspaces.test_membership_plans import member
from tests.return_helpers import make_issue_evidence, make_space, make_user
from tests.test_machine_service_workflow import machine

pytestmark = pytest.mark.django_db


def archive(user):
    # Keep the caller stale, as it is when deletion commits during another request.
    User.objects.filter(pk=user.pk).update(deletion_requested_at=timezone.now(), is_active=False)


def test_owner_guard_uses_current_database_state_and_retains_no_owner_support():
    user = make_user("obligation-guard")
    archive(user)
    with transaction.atomic(), pytest.raises(AccountDeletionPending):
        lock_obligation_owner(user)
    assert lock_obligation_owner(None) is None


@pytest.mark.parametrize("restore", [False, True])
def test_booking_create_and_restore_refuse_archived_owner(monkeypatch, restore):
    w = world(monkeypatch)
    if restore:
        w.row = bookings.cancel_booking(w.row, actor=w.grantee)
    archive(w.member)
    before = snapshot(w)
    with pytest.raises(AccountDeletionPending):
        if restore:
            bookings.restore_booking(w.row, actor=w.grantee)
        else:
            reserve(w)
    assert snapshot(w) == before


@pytest.mark.parametrize("operation", ["create", "restore", "reregister_contact"])
def test_event_registration_paths_refuse_archived_owner(operation):
    _, staff, event, owner, row = setup_restore()
    if operation != "create":
        row = events.cancel_registration(row, actor=staff)
    if operation == "reregister_contact":
        # The legacy contact-only service seam is restricted to this audience.
        event.registration_audience = "members"
        event.save(update_fields=["registration_audience"])
    archive(owner)
    before = list(EventRegistration.objects.values())
    with pytest.raises(AccountDeletionPending):
        if operation == "restore":
            from apps.events.services_registration_tools import restore_registration
            restore_registration(row, actor=staff)
        elif operation == "reregister_contact":
            events.register(event, email=row.email, name="Owner", phone="123", actor=staff,
                            staff_registration=True)
        else:
            events.register(event, member=owner, actor=staff, staff_registration=True)
    assert list(EventRegistration.objects.values()) == before


@pytest.mark.parametrize("legacy", [False, True])
def test_service_submit_refuses_member_and_legacy_owner(legacy):
    space, user = make_space("deleted-submit"), make_user("deleted-submit-owner")
    target = machine(space)
    archive(user)
    with pytest.raises(AccountDeletionPending):
        submit(target, user, member=None if legacy else user, requester_name="Owner",
               contact_email=user.email, contact_phone="123", title="Job")


def test_self_checkout_refuses_before_consuming_evidence(monkeypatch):
    space, user = make_space("deleted-self-checkout"), make_user("deleted-self-owner")
    space.enabled_features = sorted(set(space.enabled_features) | {"inventory.self_checkout"})
    space.save(update_fields=["enabled_features"])
    evidence = make_issue_evidence(space, user)
    monkeypatch.setattr("apps.hardware_requests.self_checkout_issue.validate_evidence_upload",
                        lambda *args, **kwargs: SimpleNamespace(size=10))
    archive(user)
    with pytest.raises(AccountDeletionPending):
        checkout_tool(space, user, "unused-qr", evidence_id=evidence.pk)
    evidence.refresh_from_db()
    assert evidence.consumption_state != "consumed"
    assert not HardwareRequest.objects.filter(requester=user).exists()


def test_term_purchase_and_renewal_do_not_raise_debt_for_archived_member():
    space = make_space("deleted-renewal")
    space.enabled_modules = sorted(set(space.enabled_modules) | {"membership"})
    space.enabled_features = sorted(set(space.enabled_features) | {"charges.enabled", "charges.membership"})
    space.save(update_fields=["enabled_modules", "enabled_features"])
    membership = member("deleted-renewal", space)
    plan = MembershipPlan.objects.create(makerspace=space, name="Monthly", interval="monthly", amount=10, currency="usd")
    term = create_term(None, membership, plan)
    archive(membership.user)
    with pytest.raises(AccountDeletionPending):
        create_term(None, membership, plan)
    assert raise_renewal(term) == "skipped"
    assert MembershipTerm.objects.filter(membership=membership).count() == 1
    assert not Payment.objects.filter(member=membership.user).exists()


def test_late_fee_after_departure_is_recorded_and_audited_once():
    space, actor = loan_space("deleted-late-fee", loan_late_fee_per_day=Decimal("3.00"))
    owner = make_user("deleted-late-fee-owner")
    now = timezone.now()
    row = HardwareRequest.objects.create(
        makerspace=space, requester=owner, requester_username=owner.username,
        status="returned", closed_at=now, return_due_at=now - timedelta(days=2),
    )
    archive(owner)
    first = on_request_closed(row.pk, actor, now)
    assert first is not None and first.amount == Decimal("6.00")
    assert on_request_closed(row.pk, actor, now).pk == first.pk
    entry = AuditLog.objects.get(action="account.obligation_after_deletion")
    assert entry.target_id == str(owner.pk)
    assert entry.meta["payment_id"] == first.pk


@pytest.mark.parametrize("operation", ["approve", "accept", "request"])
def test_admission_refuses_departure_before_membership_or_first_debt(operation):
    from apps.makerspaces import membership_services
    from apps.makerspaces.models import MakerspaceMembership
    from tests.makerspaces.test_membership_admission_matrix import _application, _setup
    from tests.makerspaces.test_membership_j1 import member_role

    space, actor, owner, _, _ = _setup("approval", paid=True)
    if operation == "approve":
        row = _application(space, owner)
    elif operation == "accept":
        row = membership_services.invite_membership(actor, space, owner.email, member_role(space))
    archive(owner)
    with pytest.raises(AccountDeletionPending):
        if operation == "approve":
            membership_services.approve_request(actor, row, member_role(space))
        elif operation == "accept":
            membership_services.claim_invitation(owner, row.pk)
        else:
            membership_services.request_membership(owner, space)
    assert not MakerspaceMembership.objects.filter(makerspace=space, user=owner).exists()
    assert not Payment.objects.filter(member=owner).exists()
