from tests.accounts.account_factories import make_staff
"""Alternate membership routes cannot grant or remove memberships without session proof."""
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts import reauthentication
from apps.accounts.models import User
from apps.accounts.models_reauthentication import ReauthenticationSession
from apps.audit.models import AuditLog
from apps.makerspaces.models import Makerspace, MakerspaceMembership, MakerspaceRole, MembershipRequest
from tests.accounts.test_reauthentication import PASSWORD, request

pytestmark = pytest.mark.django_db
OPERATIONS = ("invite", "approve", "revoke", "revoke_request")


@pytest.fixture
def manager(monkeypatch):
    # Only the external email transport is replaced; mutations use the real services.
    monkeypatch.setattr("apps.integrations.email.send_makerspace_email", lambda *args, **kwargs: None)
    space = Makerspace.objects.create(name="Alternate routes", slug="alternate-routes")
    user = make_staff(space, username="alternate-manager", password=PASSWORD)
    return user, space


def mutation(operation, space):
    target = User.objects.create_user(username="staff-target", email="target@example.test")
    role = MakerspaceRole.objects.get(makerspace=space, slug="member")
    membership = None
    row = None
    if operation == "revoke":
        membership = MakerspaceMembership.objects.create(
            user=target, makerspace=space, assigned_role=role, role=role.legacy_role or "custom")
    if operation in {"approve", "revoke_request"}:
        row = MembershipRequest.objects.create(
            user=target, makerspace=space, invite_email=target.email, assigned_role=role,
            kind="invite", state="invited")
    routes = {
        "invite": ("admin-membership-invitations", {"makerspace_id": space.pk},
                   {"invite_email": target.email, "role_id": role.pk}),
        "approve": ("admin-membership-request-approve", {"pk": getattr(row, "pk", None)},
                    {"role_id": role.pk}),
        "revoke": ("admin-membership-revoke-m2", {"pk": getattr(membership, "pk", None)}, {}),
        "revoke_request": ("admin-membership-request-revoke", {"pk": getattr(row, "pk", None)}, {}),
    }
    name, kwargs, body = routes[operation]
    return reverse(name, kwargs=kwargs), body, target, role, membership, row


@pytest.mark.parametrize("operation", OPERATIONS)
@pytest.mark.parametrize("proof", ["missing", "expired", "other_session", "recent"])
def test_membership_mutations_require_proof_from_this_session(manager, operation, proof):
    actor, space = manager
    url, body, target, role, membership, row = mutation(operation, space)
    req = request(actor)
    if proof != "missing":
        reauthentication.verify(request(actor) if proof == "other_session" else req, password=PASSWORD)
        if proof == "expired":
            ReauthenticationSession.objects.filter(user=actor).update(
                auth_time=timezone.now() - timedelta(minutes=11))
    client = APIClient()
    client.force_authenticate(actor, token=req.auth)
    before_audits = set(AuditLog.objects.values_list("pk", flat=True))
    before_requests = set(MembershipRequest.objects.values_list("pk", flat=True))
    response = client.post(url, body, format="json")
    if proof != "recent":
        assert response.status_code == 403
        assert response.data["code"] == "recent_reauth_required"
        assert set(AuditLog.objects.values_list("pk", flat=True)) == before_audits
        assert set(MembershipRequest.objects.values_list("pk", flat=True)) == before_requests
        if row:
            row.refresh_from_db()
            assert row.state == "invited"
        if membership:
            membership.refresh_from_db()
            assert membership.status == "active" and membership.assigned_role_id == role.pk
        else:
            assert not MakerspaceMembership.objects.filter(user=target, makerspace=space).exists()
        return

    assert response.status_code == (201 if operation == "invite" else 200), response.data
    assert set(AuditLog.objects.values_list("pk", flat=True)) > before_audits
    if operation == "invite":
        invitation = MembershipRequest.objects.get(user=target, makerspace=space)
        assert invitation.state == "invited" and invitation.assigned_role_id == role.pk
    elif operation == "revoke_request":
        row.refresh_from_db()
        assert row.state == "revoked"
        assert not MakerspaceMembership.objects.filter(user=target, makerspace=space).exists()
    else:
        changed = MakerspaceMembership.objects.get(user=target, makerspace=space)
        assert changed.assigned_role_id == role.pk
        assert changed.status == ("active" if operation == "approve" else "revoked")
        if row:
            row.refresh_from_db()
            assert row.state == ("active" if operation == "approve" else "revoked")


@pytest.mark.parametrize("operation", OPERATIONS)
def test_recent_proof_does_not_expand_membership_tenant_scope(manager, operation):
    actor, _ = manager
    foreign = Makerspace.objects.create(name="Foreign staff", slug="foreign-staff")
    url, body, target, role, membership, row = mutation(operation, foreign)
    req = request(actor)
    reauthentication.verify(req, password=PASSWORD)
    client = APIClient()
    client.force_authenticate(actor, token=req.auth)
    before_audits = set(AuditLog.objects.values_list("pk", flat=True))
    response = client.post(url, body, format="json")
    assert response.status_code == 404
    assert set(AuditLog.objects.values_list("pk", flat=True)) == before_audits
    if membership:
        membership.refresh_from_db()
        assert membership.status == "active" and membership.assigned_role_id == role.pk
    else:
        assert not MakerspaceMembership.objects.filter(user=target, makerspace=foreign).exists()
    if row:
        row.refresh_from_db()
        assert row.state == "invited"
    else:
        assert not MembershipRequest.objects.filter(user=target, makerspace=foreign).exists()


@pytest.mark.parametrize("proof", ["missing", "expired", "other_session"])
def test_active_member_request_cannot_revoke_membership_without_proof(manager, proof):
    actor, space = manager
    url, body, target, role, _, row = mutation("revoke_request", space)
    membership = MakerspaceMembership.objects.create(
        user=target, makerspace=space, assigned_role=role, role=role.legacy_role or "custom")
    row.state = "active"
    row.save(update_fields=["state"])
    req = request(actor)
    if proof != "missing":
        reauthentication.verify(request(actor) if proof == "other_session" else req, password=PASSWORD)
        if proof == "expired":
            ReauthenticationSession.objects.filter(user=actor).update(
                auth_time=timezone.now() - timedelta(minutes=11))
    client = APIClient()
    client.force_authenticate(actor, token=req.auth)
    before_audits = set(AuditLog.objects.values_list("pk", flat=True))
    response = client.post(url, body, format="json")
    assert response.status_code == 403
    assert response.data["code"] == "recent_reauth_required"
    membership.refresh_from_db()
    row.refresh_from_db()
    assert membership.status == "active" and membership.assigned_role_id == role.pk
    assert row.state == "active"
    assert set(AuditLog.objects.values_list("pk", flat=True)) == before_audits
