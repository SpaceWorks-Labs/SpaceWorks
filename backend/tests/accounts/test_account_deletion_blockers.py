"""Every account-deletion blocker uses the global owned rows and exact active states."""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.account_deletion_blockers import collect
from apps.accounts.models import User
from apps.hardware_requests.models import HardwareRequest, PublicProblemReport
from apps.makerspaces.models import MakerspaceMembership, MembershipRequest
from apps.organizations import governance
from apps.organizations.models import Organization, OrganizationMembership
from apps.payments.models import Payment, Refund
from apps.payments.services_refunds_offline import amend_offline_refund, record_offline_refund
from tests.accounts import deletion_factories as make
from tests.accounts.account_factories import make_staff
from tests.payments.test_offline_refunds import cash_deposit, payload

pytestmark = pytest.mark.django_db


def matches(user, code, **kwargs):
    return [row for row in collect(user, **kwargs) if row["code"] == code]


def test_settled_account_has_no_blockers_and_other_accounts_do_not_leak():
    user, other, tenant = make.identity(), make.identity(), make.space()
    make.payment(other, tenant)
    make.request(other, tenant, "issued")
    make.booking(other, tenant)
    make.registration(other, tenant)
    make.service_job(other, tenant)
    assert collect(user) == []


@pytest.mark.parametrize("status", Payment.Status.values)
def test_only_pending_charges_block(status):
    user, tenant = make.identity(), make.space()
    make.payment(user, tenant, status=status)
    rows = matches(user, "unpaid_charges")
    assert bool(rows) == (status == "pending")
    if rows:
        assert rows[0]["makerspace_id"] == tenant.pk and rows[0]["count"] == 1


@pytest.mark.parametrize("status", Refund.Status.values)
def test_only_pending_refunds_block(status):
    user, tenant = make.identity(), make.space()
    charge = make.payment(user, tenant, status="paid_online")
    Refund.objects.create(payment=charge, amount="2.00", currency="usd", status=status,
                          provider="stripe", created_by=user)
    assert bool(matches(user, "refund_in_progress")) == (status == "pending")


@pytest.mark.parametrize("returned,held", [("0.00", True), ("4.00", True), ("10.00", False)])
def test_deposit_held_until_fully_refunded(returned, held):
    user, tenant = make.identity(), make.space()
    charge = make.payment(user, tenant, status="paid_online", subject_type="loan_deposit")
    if Decimal(returned):
        Refund.objects.create(payment=charge, amount=returned, currency="usd", status="succeeded",
                              provider="stripe", created_by=user)
    assert bool(matches(user, "deposit_held")) == held


@pytest.mark.parametrize("status", ["pending", "waived", "canceled"])
def test_only_paid_loan_deposits_are_held(status):
    user, tenant = make.identity(), make.space()
    make.payment(user, tenant, status=status, subject_type="loan_deposit")
    assert matches(user, "deposit_held") == []


def test_paid_non_deposit_charge_does_not_hold_a_deposit():
    user, tenant = make.identity(), make.space()
    make.payment(user, tenant, status="paid_online", subject_type="loan_late_fee")
    assert matches(user, "deposit_held") == []


def test_pending_or_failed_refund_does_not_release_deposit():
    user, tenant = make.identity(), make.space()
    charge = make.payment(user, tenant, status="paid_online", subject_type="loan_deposit")
    for status in ("failed", "pending"):
        Refund.objects.create(payment=charge, amount="10.00", currency="usd", status=status,
                              provider="stripe", created_by=user)
    assert matches(user, "deposit_held")[0]["count"] == 1


def test_amended_refund_counts_only_effective_row():
    _, staff, charge = cash_deposit("deletion-effective-refund")
    first = record_offline_refund(charge, actor=staff, **payload("4.00"))
    amend_offline_refund(charge, actor=staff, refund_id=first.pk,
                         receipt=payload(method="upi", reference="correct")["receipt"])
    # Counting both immutable historical rows would falsely release this deposit.
    record_offline_refund(charge, actor=staff, **payload("2.00"))
    assert matches(charge.member, "deposit_held")[0]["count"] == 1
    record_offline_refund(charge, actor=staff, **payload("4.00"))
    assert matches(charge.member, "deposit_held") == []


@pytest.mark.parametrize("status", HardwareRequest.Status.values)
def test_hardware_request_states(status):
    user, tenant = make.identity(), make.space()
    make.request(user, tenant, status)
    assert bool(matches(user, "active_loans")) == (status in {"issued", "partially_returned"})
    assert bool(matches(user, "open_requests")) == (status in {"draft", "pending_approval", "accepted"})


@pytest.mark.parametrize("status,blocked", [("checked_out", True), ("returned", False)])
def test_public_loan_states(status, blocked):
    user, tenant = make.identity(), make.space()
    make.loan(user, tenant, status)
    assert bool(matches(user, "active_loans")) == blocked


def test_active_loan_counts_merge_sources_and_remain_per_tenant():
    user, a, b = make.identity(), make.space(), make.space()
    make.request(user, a, "issued")
    make.loan(user, a, "checked_out")
    make.request(user, b, "partially_returned")
    rows = matches(user, "active_loans")
    assert {row["makerspace_id"]: row["count"] for row in rows} == {a.pk: 2, b.pk: 1}


@pytest.mark.parametrize("resolved", [True, False])
def test_only_unresolved_problem_reports_block(resolved):
    user, tenant = make.identity(), make.space()
    loan = make.loan(user, tenant)
    PublicProblemReport.objects.create(
        makerspace=tenant, requester=user, loan=loan, request=loan.request,
        note="Damaged", resolved_at=timezone.now() if resolved else None,
    )
    assert bool(matches(user, "problem_report_open")) == (not resolved)


@pytest.mark.parametrize("status", User.AccessStatus.values)
def test_restricted_or_suspended_access_blocks(status):
    user = make.identity()
    user.access_status = status
    user.save(update_fields=["access_status"])
    assert bool(matches(user, "access_restricted")) == (status != "active")


@pytest.mark.parametrize("legacy", [True, False])
@pytest.mark.parametrize("status", ["pending", "accepted", "in_progress", "completed", "collected", "rejected", "failed"])
def test_service_job_states_include_uncollected_completion_and_legacy_owner(status, legacy):
    user, tenant = make.identity(), make.space()
    make.service_job(user, tenant, status=status, legacy=legacy)
    assert bool(matches(user, "open_service_jobs")) == (status in {"pending", "accepted", "in_progress", "completed"})


def test_staff_requester_does_not_own_somebody_elses_member_service_job():
    user, other, tenant = make.identity(), make.identity(), make.space()
    make.service_job(other, tenant, requester=user)
    assert matches(user, "open_service_jobs") == []
    assert matches(other, "open_service_jobs")[0]["count"] == 1


@pytest.mark.parametrize("status", ["pending", "confirmed", "rejected", "cancelled", "completed", "no_show"])
@pytest.mark.parametrize("future", [True, False])
def test_booking_requires_live_status_and_future_end(status, future):
    user, tenant, now = make.identity(), make.space(), timezone.now()
    make.booking(user, tenant, status=status, ends_at=now + timedelta(days=1) if future else now)
    assert bool(matches(user, "upcoming_bookings", now=now)) == (future and status in {"pending", "confirmed"})


@pytest.mark.parametrize("status", ["pending_approval", "registered", "waitlisted", "rejected", "cancelled", "attended"])
def test_registration_active_states(status):
    user, tenant = make.identity(), make.space()
    make.registration(user, tenant, status=status)
    assert bool(matches(user, "upcoming_registrations")) == (status in {"pending_approval", "registered", "waitlisted"})


@pytest.mark.parametrize("event_status", ["draft", "published", "cancelled", "completed"])
@pytest.mark.parametrize("future", [True, False])
def test_registration_requires_draft_or_published_event_with_future_end(event_status, future):
    user, tenant, now = make.identity(), make.space(), timezone.now()
    make.registration(user, tenant, event_status=event_status,
                      ends_at=now + timedelta(days=1) if future else now)
    assert bool(matches(user, "upcoming_registrations", now=now)) == (future and event_status in {"draft", "published"})


def test_last_manager_blocks_until_another_eligible_action_holder_exists():
    tenant = make.space()
    user = make_staff(tenant, username="blocker-manager")
    assert matches(user, "last_manager")[0]["makerspace_id"] == tenant.pk
    successor = make_staff(tenant, username="blocker-successor")
    assert matches(user, "last_manager") == []


@pytest.mark.parametrize("change", ["revoked", "inactive", "restricted", "stub", "nonmanager"])
def test_ineligible_successor_never_satisfies_last_manager_rule(change):
    tenant = make.space()
    user = make_staff(tenant, username="blocker-manager")
    successor = make_staff(tenant, username="blocker-successor",
                           role_slug="inventory_manager" if change == "nonmanager" else "space_manager")
    if change == "revoked":
        MakerspaceMembership.staff_tracks.filter(user=successor).update(status="revoked")
    if change == "inactive":
        successor.is_active = False
    if change == "restricted":
        successor.access_status = "restricted"
    if change == "stub":
        successor.is_tenant_dump_stub = True
    successor.save()
    assert matches(user, "last_manager")


def test_revoked_manager_membership_does_not_block():
    tenant = make.space()
    user = make_staff(tenant, username="blocker-revoked-manager")
    MakerspaceMembership.staff_tracks.filter(user=user).update(status="revoked")
    assert matches(user, "last_manager") == []


def test_last_governor_uses_existing_rule_and_another_governor_allows_departure():
    user, other = make.identity(), make.identity()
    org = Organization.objects.create(name="Deletion org", slug="deletion-org")
    OrganizationMembership.objects.create(user=user, organization=org,
        governance_actions=[governance.MANAGE_ORGANIZATION_MEMBERS])
    assert matches(user, "last_org_governor")[0]["organization_id"] == org.pk
    other_member = OrganizationMembership.objects.create(user=other, organization=org,
        governance_actions=[governance.MANAGE_ORGANIZATION_MEMBERS], status="suspended")
    assert matches(user, "last_org_governor")
    other_member.status = "active"
    other_member.save(update_fields=["status"])
    assert matches(user, "last_org_governor") == []


def test_ordinary_org_member_does_not_block_and_explicit_org_list_stays_owned():
    user = make.identity()
    org = Organization.objects.create(name="Ordinary", slug="ordinary")
    OrganizationMembership.objects.create(user=user, organization=org)
    foreign = Organization.objects.create(name="Foreign", slug="foreign")
    OrganizationMembership.objects.create(user=make.identity(), organization=foreign,
        governance_actions=[governance.MANAGE_ORGANIZATION_MEMBERS])
    assert matches(user, "last_org_governor", organizations=[org, foreign]) == []


def test_inactive_organization_still_preserves_its_last_governor():
    user = make.identity()
    org = Organization.objects.create(name="Inactive", slug="inactive", is_active=False)
    OrganizationMembership.objects.create(user=user, organization=org,
        governance_actions=[governance.MANAGE_ORGANIZATION_MEMBERS])
    assert matches(user, "last_org_governor")[0]["organization_id"] == org.pk


def test_gated_spaces_are_reported_in_sorted_order_and_clear_when_reopened():
    user = make.identity()
    rows = matches(user, "makerspace_gated", gated={8, 3})
    assert [row["makerspace_id"] for row in rows] == [3, 8]
    assert all(row["organization_id"] is None and row["count"] == 1 and row["detail"] for row in rows)
    assert matches(user, "makerspace_gated") == []


def test_platform_flags_identify_one_immutable_platform_principal():
    user = User.objects.create_superuser(username="blocker-platform")
    assert user.is_superuser and user.role == User.Role.SUPERADMIN
    assert matches(user, "superadmin")[0]["makerspace_id"] is None



@pytest.mark.parametrize("state", ["requested", "invited", "awaiting_vouches"])
def test_open_applications_are_closed_by_deletion_instead_of_becoming_blockers(state):
    user, tenant = make.identity(), make.space()
    MembershipRequest.objects.create(user=user, makerspace=tenant, state=state, kind="request")
    assert collect(user) == []
