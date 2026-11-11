from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from django.utils import timezone
import pytest
from rest_framework.exceptions import PermissionDenied

from apps.accounts.security_activity import SecurityActivitySerializer, own_security_activity
from apps.audit.services import record
from apps.operations.platform_insights import platform_insights
from apps.organizations import governance, member_leave
from apps.organizations.models import Organization, OrganizationMembership
from apps.organizations.services_console import OrganizationConflict
from tests.events.ticketing_helpers import account, event_space


@pytest.mark.django_db
def test_security_activity_is_owner_allowlist_and_never_contains_metadata():
    actor, foreign = account("security-owner"), account("security-foreign")
    safe = record(actor, "auth.login_succeeded", target=actor, meta={"secret": "never expose"})
    record(foreign, "auth.login_succeeded", target=foreign)
    record(actor, "event.registration_created", target=actor, meta={"email": "private@example.test"})
    rows = own_security_activity(actor)
    assert list(rows.values_list("pk", flat=True)) == [safe.pk]
    assert set(SecurityActivitySerializer(rows[0]).data) == {"id", "action", "created_at"}


@pytest.mark.django_db
@pytest.mark.parametrize("action", ["user.password_changed", "user.password_reset_via_email", "user.password_reset"])
def test_actual_password_action_names_are_visible_only_to_the_actor(action):
    actor, foreign = account("password-owner"), account("password-foreign")
    own = record(actor, action, target=actor)
    record(foreign, action, target=foreign)
    assert list(own_security_activity(actor).values_list("pk", flat=True)) == [own.pk]


@pytest.mark.django_db
def test_sole_governor_cannot_leave_but_second_governor_can(monkeypatch):
    actor, second = account("org-owner"), account("org-successor")
    organization = Organization.objects.create(name="Workshop org", slug="workshop-org")
    membership = OrganizationMembership.objects.create(organization=organization, user=actor,
        governance_actions=[governance.MANAGE_ORGANIZATION_MEMBERS])
    monkeypatch.setattr(member_leave, "require_recent_reauth", Mock())
    request = SimpleNamespace(user=actor)
    version = member_leave.membership_version(membership)
    projected = member_leave.project_leave_state(organization, actor)
    assert projected["membership_version"] == version
    assert projected["reason"] == "sole_owner" and projected["allowed_actions"] == []
    with pytest.raises(OrganizationConflict):
        member_leave.leave_organization(request=request, organization_id=organization.pk,
                                        operation_id=uuid4(), expected_version=version)
    assert OrganizationMembership.objects.filter(pk=membership.pk).exists()
    OrganizationMembership.objects.create(organization=organization, user=second,
        governance_actions=[governance.MANAGE_ORGANIZATION_MEMBERS])
    assert member_leave.project_leave_state(organization, actor)["allowed_actions"] == ["leave"]
    operation = uuid4()
    result = member_leave.leave_organization(request=request, organization_id=organization.pk,
                                            operation_id=operation, expected_version=version)
    assert result["state"] == "left"
    assert not OrganizationMembership.objects.filter(pk=membership.pk).exists()
    assert member_leave.leave_organization(request=request, organization_id=organization.pk,
        operation_id=operation, expected_version=version) == result
    assert not governance.actions_for(actor, organization)


@pytest.mark.django_db
def test_leave_requires_recent_reauth_before_membership_mutation(monkeypatch):
    actor = account("reauth-owner")
    organization = Organization.objects.create(name="Proof org", slug="proof-org")
    membership = OrganizationMembership.objects.create(organization=organization, user=actor)
    monkeypatch.setattr(member_leave, "require_recent_reauth", Mock(side_effect=PermissionDenied()))
    with pytest.raises(PermissionDenied):
        member_leave.leave_organization(request=SimpleNamespace(user=actor), organization_id=organization.pk,
            operation_id=uuid4(), expected_version=member_leave.membership_version(membership))
    assert OrganizationMembership.objects.filter(pk=membership.pk).exists()


@pytest.mark.django_db
def test_platform_counts_reject_tenant_staff():
    from tests.events.collab_helpers import make_staff
    from apps.accounts.models import User
    from apps.accounts.models_mfa import UserMFA
    visible = event_space("insights-visible")
    staff = make_staff(visible)
    UserMFA.objects.create(user=staff, secret="ciphertext-not-read", enabled_at=timezone.now())
    platform = User.objects.create_superuser(username="insights-platform", password="password-for-test",
                                              email="platform@example.test")
    with pytest.raises(PermissionDenied):
        platform_insights(staff)
    result = platform_insights(platform)
    assert result["staff_mfa"]["active"] == 1
    assert result["staff_mfa"]["enabled"] == 1
    assert sum(point["makerspaces"] for point in result["growth"]) == 1
    assert "ciphertext-not-read" not in str(result)
    assert "@example.test" not in str(result)
    assert len(result["growth"]) == 30
