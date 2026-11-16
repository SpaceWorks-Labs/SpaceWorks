"""Each global blocker is checked both in preview and under Stage A's locks."""

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.accounts import account_deletion as deletion
from apps.accounts.account_deletion_blockers import collect
from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.hardware_requests.models import PublicProblemReport
from apps.makerspaces.models import MakerspaceMembership
from apps.organizations.governance import MANAGE_ORGANIZATION_MEMBERS
from apps.organizations.models import Organization, OrganizationMembership
from apps.payments.models import Payment, Refund
from apps.payments.services_refunds_offline import amend_offline_refund, record_offline_refund
from apps.tenant_migration.models_source_gate import SourceMigrationGate
from tests.accounts import deletion_factories as f
from tests.accounts.test_support_m1d import account, m1d_config, proven
from tests.accounts.account_factories import make_staff, make_membership
from tests.payments.test_offline_refunds import cash_deposit, payload

pytestmark = pytest.mark.django_db

CASES = [
    ("unpaid_charges", "payment"), ("refund_in_progress", "refund"),
    ("deposit_held", "deposit"), ("active_loans", "request_loan"),
    ("active_loans", "public_loan"), ("open_requests", "request"),
    ("problem_report_open", "problem"), ("access_restricted", "access"),
    ("open_service_jobs", "service"), ("open_service_jobs", "legacy_service"),
    ("upcoming_bookings", "booking"), ("upcoming_registrations", "registration"),
    ("last_org_governor", "governor"), ("makerspace_gated", "gate"),
]


def arrange(user, tenant, kind, enabled):
    if kind == "payment":
        f.payment(user, tenant, status="pending" if enabled else "paid_offline")
    elif kind in {"refund", "deposit"}:
        charge = f.payment(user, tenant, status="paid_online",
                           subject_type="loan_deposit" if kind == "deposit" else "loan_late_fee")
        Refund.objects.create(payment=charge, amount="10.00", currency="usd", created_by=user,
                              provider="stripe", status="pending" if enabled else "succeeded")
    elif kind in {"request", "request_loan"}:
        f.request(user, tenant, ("accepted" if kind == "request" else "issued") if enabled else "returned")
    elif kind == "public_loan":
        f.loan(user, tenant, "checked_out" if enabled else "returned")
    elif kind == "problem":
        loan = f.loan(user, tenant)
        PublicProblemReport.objects.create(makerspace=tenant, requester=user, loan=loan,
            request=loan.request, note="Broken", resolved_at=None if enabled else timezone.now())
    elif kind == "access":
        user.access_status = "restricted" if enabled else "active"
        user.save(update_fields=["access_status"])
    elif kind in {"service", "legacy_service"}:
        f.service_job(user, tenant, legacy=kind == "legacy_service", status="completed" if enabled else "collected")
    elif kind == "booking":
        f.booking(user, tenant, status="confirmed" if enabled else "completed")
    elif kind == "registration":
        f.registration(user, tenant, status="registered" if enabled else "cancelled")
    elif kind == "governor":
        org = Organization.objects.create(name="Governance", slug="gov-" + uuid4().hex)
        for holder in [user] + ([] if enabled else [account()]):
            OrganizationMembership.objects.create(organization=org, user=holder,
                governance_actions=[MANAGE_ORGANIZATION_MEMBERS])
    elif kind == "gate":
        make_membership(user, tenant, status="revoked")
        if enabled:
            now = timezone.now()
            SourceMigrationGate.objects.create(makerspace=tenant, state="quiesced", owner_id=uuid4(),
                heartbeat_at=now, lease_expires_at=now + timedelta(hours=1))



@pytest.mark.parametrize("code,kind", CASES, ids=[kind for _, kind in CASES])
@pytest.mark.parametrize("enabled", [True, False], ids=["blocked", "clear"])
def test_preview_and_locked_stage_a_agree_on_each_blocker(code, kind, enabled, monkeypatch):
    user, tenant = account(), f.space()
    # Establish proof first: restricted accounts cannot start a new auth session.
    req = proven(user)
    arrange(user, tenant, kind, enabled)
    req.user.refresh_from_db()
    preview = deletion.preview(req)
    assert (code in {row["code"] for row in preview["blockers"]}) is enabled
    if kind == "access" and enabled:
        # An already restricted account cannot authenticate. Model a restriction
        # arriving after initial proof verification, before the locked recheck.
        user.access_status = "active"
        user.save(update_fields=["access_status"])
        req.user.refresh_from_db()
        real_gates = deletion._gates

        def restrict_after_initial_proof(ids):
            result = real_gates(ids)
            type(user).objects.filter(pk=user.pk).update(access_status="restricted")
            return result

        monkeypatch.setattr(deletion, "_gates", restrict_after_initial_proof)
    if enabled:
        with pytest.raises(deletion.DeletionBlocked) as failure:
            deletion.request_deletion(req)
        assert code in {row["code"] for row in failure.value.blockers}
        user.refresh_from_db()
        assert user.deletion_requested_at is None and user.is_active
        audit = AuditLog.objects.get(action="account.deletion_refused", actor=user)
        assert code in audit.meta["blocker_codes"]
    else:
        assert preview["blockers"] == []
        assert deletion.request_deletion(req)["deleted_at"]
        user.refresh_from_db()
        assert not user.is_active


@pytest.mark.parametrize("status", ["draft", "pending_approval", "accepted", "issued", "partially_returned",
                                   "returned", "rejected", "closed_with_issue"])
def test_request_state_partition(status):
    user, tenant = account(), f.space()
    f.request(user, tenant, status)
    codes = {row["code"] for row in collect(user)}
    assert ("open_requests" in codes) is (status in {"draft", "pending_approval", "accepted"})
    assert ("active_loans" in codes) is (status in {"issued", "partially_returned"})


@pytest.mark.parametrize("legacy", [True, False])
@pytest.mark.parametrize("status", ["pending", "accepted", "in_progress", "completed", "collected", "rejected", "failed"])
def test_service_uncollected_completion_and_legacy_ownership(status, legacy):
    user, tenant = account(), f.space()
    f.service_job(user, tenant, status=status, legacy=legacy)
    assert bool(collect(user)) is (status in {"pending", "accepted", "in_progress", "completed"})


@pytest.mark.parametrize("domain", ["booking", "registration"])
@pytest.mark.parametrize("future", [True, False])
@pytest.mark.parametrize("live", [True, False])
def test_time_and_status_both_required(domain, future, live):
    user, tenant, now = account(), f.space(), timezone.now()
    end = now + timedelta(days=1) if future else now
    if domain == "booking":
        f.booking(user, tenant, ends_at=end, status="pending" if live else "cancelled")
    else:
        f.registration(user, tenant, ends_at=end, event_status="draft" if live else "completed")
    assert bool(collect(user, now=now)) is (future and live)


def test_effective_refund_math_does_not_double_count_amended_receipts():
    _, staff, deposit = cash_deposit("m1d-effective")
    old = record_offline_refund(deposit, actor=staff, **payload("4.00"))
    amended = amend_offline_refund(deposit, actor=staff, refund_id=old.pk,
        receipt=payload(method="upi", reference="corrected-m1d")["receipt"])
    record_offline_refund(deposit, actor=staff, **payload("2.00"))
    assert Refund.counted_total(deposit) == Decimal("6.00")
    assert "deposit_held" in {row["code"] for row in collect(deposit.member)}
    record_offline_refund(deposit, actor=staff, **payload("4.00"))
    assert Refund.counted_total(deposit) == deposit.amount
    assert "deposit_held" not in {row["code"] for row in collect(deposit.member)}
    old.refresh_from_db()
    assert old.amended_by.pk == amended.pk


@pytest.mark.parametrize("status", Payment.Status.values)
def test_only_pending_ledger_status_blocks_payment(status):
    user, tenant = account(), f.space()
    f.payment(user, tenant, status=status)
    assert bool(collect(user)) is (status == "pending")


@pytest.mark.parametrize("status", Refund.Status.values)
def test_only_pending_refunds_block_and_only_succeeded_refunds_release_deposits(status):
    user, tenant = account(), f.space()
    payment = f.payment(user, tenant, status="paid_offline", subject_type="loan_deposit")
    Refund.objects.create(payment=payment, amount="10.00", currency="usd", status=status,
        provider="stripe", created_by=user)
    codes = {row["code"] for row in collect(user)}
    assert ("refund_in_progress" in codes) is (status == "pending")
    assert ("deposit_held" in codes) is (status != "succeeded")


@pytest.mark.parametrize("status", ["pending_approval", "registered", "waitlisted", "rejected", "cancelled", "attended"])
def test_registration_blocker_includes_approval_and_waitlist(status):
    user, tenant = account(), f.space()
    f.registration(user, tenant, status=status)
    assert bool(collect(user)) is (status in {"pending_approval", "registered", "waitlisted"})


@pytest.mark.parametrize("status", ["pending", "confirmed", "rejected", "cancelled", "completed", "no_show"])
def test_booking_blocker_includes_pending_approval(status):
    user, tenant = account(), f.space()
    f.booking(user, tenant, status=status)
    assert bool(collect(user)) is (status in {"pending", "confirmed"})


@pytest.mark.parametrize("status", User.AccessStatus.values)
def test_every_account_restriction_status(status):
    user = account()
    user.access_status = status
    user.save(update_fields=["access_status"])
    assert bool(collect(user)) is (status != "active")


@pytest.mark.parametrize("defect", ["inactive", "revoked", "restricted", "stub", "wrong_role"])
def test_last_manager_requires_an_eligible_successor(defect):
    tenant = f.space()
    user = make_staff(tenant, username="blocker-manager")
    successor = make_staff(tenant, username="blocker-successor",
                           role_slug="handover" if defect == "wrong_role" else "space_manager")
    # #63 (U-A1 11c64a43): staff roles are staff-track rows the default manager does not return.
    from apps.makerspaces.models import MakerspaceMembership
    replacement = MakerspaceMembership.staff_tracks.get(user=successor, makerspace=tenant)
    if defect == "revoked":
        replacement.status = "revoked"
        replacement.save(update_fields=["status"])
    elif defect in {"inactive", "restricted", "stub"}:
        changes = {"inactive": {"is_active": False}, "restricted": {"access_status": "restricted"},
                   "stub": {"is_tenant_dump_stub": True}}[defect]
        User.objects.filter(pk=successor.pk).update(**changes)
    assert [row["code"] for row in collect(user)] == ["last_manager"]
