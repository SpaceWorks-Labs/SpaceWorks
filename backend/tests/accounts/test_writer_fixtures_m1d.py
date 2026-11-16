"""Build obligations through the same domain helpers as their workflow suites."""

from types import SimpleNamespace

from apps.bookings import services as bookings
from apps.events import services as events
from apps.events.models import EventRegistration
from apps.events.services_registration_tools import restore_registration
from apps.hardware_requests.models import HardwareRequest
from apps.hardware_requests.self_checkout_issue import checkout_tool
from apps.machines.models import MachineServiceRequest
from apps.machines.service_workflow import submit
from apps.makerspaces import membership_services
from apps.makerspaces.membership_plan_services import create_term
from apps.makerspaces.membership_renewal_charges import raise_renewal
from apps.makerspaces.models import MembershipPlan, MembershipTerm
from apps.payments.models import Payment
from tests.accounts.test_account_obligation_races import _writer
from tests.accounts.test_support_m1d import account
from tests.bookings.test_staff_tools_helpers import reserve, world
from tests.events.test_lane_b_restore import setup_restore
from tests.fixed_roles.helpers import assign_builtin_roles
from tests.makerspaces.test_membership_admission_matrix import _application, _setup
from tests.makerspaces.test_membership_j1 import member_role
from tests.return_helpers import make_issue_evidence, make_space
from tests.test_machine_service_workflow import machine


WRITERS = ["request", "direct_handout", "self_checkout", "service_submit", "legacy_submit",
           "reprint", "legacy_reprint", "booking_create", "booking_restore", "event_create",
           "event_restore", "plan_purchase", "renewal", "admission_approve", "admission_accept",
           "admission_request"]


def writer_case(kind, monkeypatch):
    """Return tenant, stale owner, write callable and an obligation snapshot."""
    if kind.startswith("booking_"):
        w = world(monkeypatch)
        row = bookings.cancel_booking(w.row, actor=w.grantee)
        write = (lambda: reserve(w)) if kind == "booking_create" else (
            lambda: bookings.restore_booking(row, actor=w.grantee))
        return w.tenant, w.member, write, lambda: list(
            row.__class__.objects.filter(member=w.member).values("pk", "status"))
    if kind.startswith("event_"):
        tenant, actor, event, owner, row = setup_restore()
        row = events.cancel_registration(row, actor=actor)
        write = (lambda: events.register(event, member=owner, actor=actor, staff_registration=True)) if (
            kind == "event_create") else lambda: restore_registration(row, actor=actor)
        return tenant, owner, write, lambda: list(EventRegistration.objects.filter(member=owner).values("pk", "status"))
    if kind.startswith("admission_"):
        tenant, actor, owner, _, _ = _setup("approval", paid=True)
        if kind == "admission_approve":
            row = _application(tenant, owner)
            write = lambda: membership_services.approve_request(actor, row, member_role(tenant))
        elif kind == "admission_accept":
            row = membership_services.invite_membership(actor, tenant, owner.email, member_role(tenant))
            write = lambda: membership_services.claim_invitation(owner, row.pk)
        else:
            write = lambda: membership_services.request_membership(owner, tenant)
        return tenant, owner, write, lambda: list(Payment.objects.filter(member=owner).values())
    tenant, owner, actor = make_space("race-" + kind), account(), account()
    if kind in {"plan_purchase", "renewal"}:
        tenant.enabled_modules = sorted(set(tenant.enabled_modules) | {"membership"})
        tenant.enabled_features = sorted(set(tenant.enabled_features) | {"charges.enabled", "charges.membership"})
        tenant.save()
        membership = assign_builtin_roles(owner, tenant, "member")
        plan = MembershipPlan.objects.create(makerspace=tenant, name="Monthly", interval="monthly", amount=10, currency="usd")
        term = create_term(None, membership, plan)
        write = (lambda: create_term(None, membership, plan)) if kind == "plan_purchase" else lambda: raise_renewal(term)
        return tenant, owner, write, lambda: (
            MembershipTerm.objects.filter(membership=membership).count(), Payment.objects.filter(member=owner).count())
    if kind == "self_checkout":
        tenant.enabled_features = sorted(set(tenant.enabled_features) | {"inventory.self_checkout"})
        tenant.save()
        evidence = make_issue_evidence(tenant, owner)
        monkeypatch.setattr("apps.hardware_requests.self_checkout_issue.validate_evidence_upload",
                            lambda *a, **kw: SimpleNamespace(size=10))
        write = lambda: checkout_tool(tenant, owner, "unused-qr", evidence_id=evidence.pk)
        return tenant, owner, write, lambda: (HardwareRequest.objects.filter(requester=owner).count(),
            evidence.__class__.objects.get(pk=evidence.pk).consumption_state)
    if kind in {"service_submit", "legacy_submit"}:
        target = machine(tenant)
        write = lambda: submit(target, owner, member=owner if kind == "service_submit" else None,
            requester_name="Owner", contact_email=owner.email, contact_phone="123", title="Job")
        return tenant, owner, write, lambda: MachineServiceRequest.objects.filter(requester=owner).count()
    write, snapshot = _writer(kind, tenant, owner, actor, monkeypatch)
    return tenant, owner, write, snapshot
