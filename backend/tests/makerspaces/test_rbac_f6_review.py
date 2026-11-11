"""Regression coverage for delegated authority boundaries found during F6 review."""
import pytest
from django.utils import timezone
from django.db import IntegrityError, connection, transaction

from apps.audit.models import AuditLog
from apps.makerspaces.models import MakerspaceMembership, MembershipPlan
from tests.rbac_f6_helpers import community_member, custom_actor
from tests.return_helpers import authenticated_client, make_space, make_user

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("method", ["post", "patch"])
def test_plan_definition_authority_is_independent_of_roster_grants(method):
    space = make_space(f"f6-plan-definition-{method}")
    actor = custom_actor(space, ["manage_makerspace"])
    client = authenticated_client(actor)
    if method == "post":
        path = f"/api/v1/admin/makerspaces/{space.pk}/membership-plans"
        body = {"name": "Monthly", "interval": "monthly", "amount": "20.00", "currency": "usd"}
    else:
        plan = MembershipPlan.objects.create(makerspace=space, name="Monthly", interval="monthly", amount="10.00", currency="usd")
        path = f"/api/v1/admin/membership-plans/{plan.pk}"
        body = {"amount": "20.00"}
    response = getattr(client, method)(path, body, format="json")
    assert response.status_code == (201 if method == "post" else 200), response.data
    plan = MembershipPlan.objects.get(makerspace=space, name="Monthly")
    assert plan.amount == 20
    assert AuditLog.objects.filter(
        actor=actor, makerspace=space,
        action=f"membership_plan.{'created' if method == 'post' else 'updated'}",
        target_id=str(plan.pk),
    ).exists()


@pytest.mark.parametrize("method", ["post", "patch"])
def test_plan_definition_and_audit_roll_back_together(method, monkeypatch):
    space = make_space(f"f6-plan-audit-{method}")
    actor = custom_actor(space, ["manage_makerspace"])
    if method == "post":
        path = f"/api/v1/admin/makerspaces/{space.pk}/membership-plans"
        body = {"name": "Monthly", "interval": "monthly", "amount": "20.00", "currency": "usd"}
    else:
        plan = MembershipPlan.objects.create(makerspace=space, name="Monthly", interval="monthly", amount="10.00", currency="usd")
        path = f"/api/v1/admin/membership-plans/{plan.pk}"
        body = {"amount": "20.00"}

    def fail_audit(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr("apps.admin_api.views_membership_plans.audit.record", fail_audit)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        getattr(authenticated_client(actor), method)(path, body, format="json")
    if method == "post":
        assert not MembershipPlan.objects.filter(makerspace=space, name="Monthly").exists()
    else:
        plan.refresh_from_db()
        assert plan.amount == 10


def test_coordinator_can_verify_staff_without_changing_their_role():
    space = make_space("f6-staff-verification")
    actor = custom_actor(space, ["manage_members"])
    staff = custom_actor(space, ["edit_inventory"], name="inventory-staff")
    membership = MakerspaceMembership.objects.get(makerspace=space, user=staff)
    original_role = membership.assigned_role_id
    response = authenticated_client(actor).post(
        f"/api/v1/admin/memberships/{membership.pk}/verify", {}, format="json",
    )
    assert response.status_code == 200
    membership.refresh_from_db()
    assert membership.verified_at is not None
    assert membership.assigned_role_id == original_role
    assert AuditLog.objects.filter(actor=actor, action="membership.verified", target_id=str(membership.pk)).exists()


def test_presence_roster_only_lists_the_authorized_space():
    from datetime import timedelta
    from apps.presence.models import PresenceSession

    space = make_space("f6-presence-local")
    other = make_space("f6-presence-foreign")
    actor = custom_actor(space, ["manage_members"])
    account_ids = {}
    for tenant in (space, other):
        member = community_member(tenant)
        account_ids[tenant.pk] = member.user_id
        PresenceSession.objects.create(
            makerspace=tenant, membership=member, member=member.user,
            started_at=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=1),
        )
    client = authenticated_client(actor)
    response = client.get(f"/api/v1/admin/makerspace/{space.pk}/presence-sessions/current")
    assert response.status_code == 200
    assert response.data["count"] == 1
    assert len(response.data["results"]) == 1
    assert response.data["results"][0]["account_id"] == account_ids[space.pk]
    assert client.get(f"/api/v1/admin/makerspace/{other.pk}/presence-sessions/current").status_code == 404


def test_superadmin_cannot_hold_a_delegated_verifier_membership():
    space = make_space("f6-superadmin-verifier")
    member = community_member(space)
    actor = make_user("f6-superadmin-delegate", role="superadmin", access_status="active")
    with pytest.raises(IntegrityError), transaction.atomic():
        MakerspaceMembership.objects.create(
            makerspace=space, user=actor, role="custom", can_verify=True,
            assigned_role=member.assigned_role,
        )
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")


@pytest.mark.parametrize("operation", ["verify", "unverify", "refer", "verifier"])
def test_verification_services_recheck_the_locked_module_gate(operation):
    from rest_framework.exceptions import ValidationError
    from apps.makerspaces import membership_services
    from tests.module_helpers import disable_module

    space = make_space(f"f6-verification-off-{operation}")
    member = community_member(space)
    actor = custom_actor(space, ["manage_members"])
    MakerspaceMembership.objects.filter(pk=member.pk).update(can_refer=False, can_verify=False)
    disable_module(space, "membership")
    operations = {
        "verify": lambda: membership_services.verify_member(actor, member),
        "unverify": lambda: membership_services.unverify_member(actor, member),
        "refer": lambda: membership_services.set_can_refer(actor, member, True),
        "verifier": lambda: membership_services.set_can_verify(actor, member, True),
    }
    with pytest.raises(ValidationError):
        operations[operation]()
    member.refresh_from_db()
    assert member.verified_at is None
    assert not member.can_refer and not member.can_verify
    assert not AuditLog.objects.filter(actor=actor, makerspace=space).exists()
