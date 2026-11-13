from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import close_old_connections
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.organizations.governance import GOVERNANCE_ACTIONS
from apps.organizations.models import Organization, OrganizationMembership
from apps.organizations.services_console import OrganizationConflict
from apps.organizations.services_governance import delete_organization
from apps.organizations.services_self_service import create_self_service

pytestmark = pytest.mark.django_db


def account(name="creator"):
    actor = User.objects.create_user(username=name, email=f"{name}@example.test")
    User.objects.filter(pk=actor.pk).update(email_verified_at=timezone.now())
    actor.refresh_from_db()
    return actor


def test_self_creation_is_off_by_default_and_does_not_write(settings):
    settings.ORGANIZATION_SELF_CREATION_ENABLED = False
    with pytest.raises(PermissionDenied):
        create_self_service(account(), name="Private", slug="private")
    assert not Organization.objects.exists()


@pytest.mark.parametrize("change", [
    {"email_verified_at": None}, {"is_active": False},
    {"access_status": User.AccessStatus.RESTRICTED}, {"must_change_password": True}, {"is_tenant_dump_stub": True},
])
def test_only_live_verified_unrestricted_accounts_can_create(settings, change):
    settings.ORGANIZATION_SELF_CREATION_ENABLED = True
    actor = account()
    User.objects.filter(pk=actor.pk).update(**change)
    with pytest.raises(PermissionDenied):
        create_self_service(actor, name="Private", slug="private")
    assert not Organization.objects.exists()


def test_new_organization_has_only_governance_and_is_private(settings):
    settings.ORGANIZATION_SELF_CREATION_ENABLED = True
    actor = account()
    row = create_self_service(actor, name="Private", slug="private")
    member = OrganizationMembership.objects.get(organization=row, user=actor)
    assert set(member.governance_actions) == GOVERNANCE_ACTIONS
    assert member.granted_actions == []
    assert not row.public_profile_enabled
    assert not row.makerspace_links.exists()
    assert AuditLog.objects.filter(actor=actor, action="organization.self_created").count() == 1
    assert AuditLog.objects.filter(actor=actor, action="organization.membership_created").count() == 1


def test_deletion_does_not_reset_daily_limit(settings):
    settings.ORGANIZATION_SELF_CREATION_ENABLED = True
    settings.ORGANIZATION_SELF_CREATION_MAX_PER_DAY = 1
    actor = account()
    row = create_self_service(actor, name="Private", slug="private")
    delete_organization(row, actor=actor)
    with pytest.raises(OrganizationConflict):
        create_self_service(actor, name="Second", slug="second")
    assert AuditLog.objects.filter(action="organization.deleted").exists()


def test_owned_limit_and_conflict_rollback(settings):
    settings.ORGANIZATION_SELF_CREATION_ENABLED = True
    settings.ORGANIZATION_SELF_CREATION_MAX_PER_DAY = 10
    settings.ORGANIZATION_SELF_CREATION_MAX_OWNED = 1
    actor = account()
    create_self_service(actor, name="Private", slug="private")
    with pytest.raises(OrganizationConflict):
        create_self_service(actor, name="Second", slug="second")
    assert OrganizationMembership.objects.filter(user=actor).count() == 1


def test_http_policy_and_creation_do_not_grant_tenant_authority(settings):
    settings.ORGANIZATION_SELF_CREATION_ENABLED = True
    client = APIClient()
    url = reverse("auth-organizations-self-service")
    assert client.post(url, {"name": "Private", "slug": "private"}).status_code in (401, 403)
    client.force_authenticate(account())
    assert client.get(url).data["eligible"] is True
    created = client.post(url, {"name": "Private", "slug": "private", "public_profile_enabled": True,
                                "granted_actions": ["manage_makerspace"]}, format="json")
    assert created.status_code == 201
    assert created.data["granted_actions"] == []
    assert created.data["public_profile_enabled"] is False
    assert client.post(reverse("admin-organization-links", kwargs={"pk": created.data["id"]}),
                       {"makerspace_id": 1, "relationship": "owner"}, format="json").status_code == 403


def test_creation_refuses_makerspace_custom_origin(settings):
    from apps.makerspaces.models import Makerspace
    settings.ORGANIZATION_SELF_CREATION_ENABLED = True
    Makerspace.objects.create(name="Scoped", slug="scoped", frontend_domain="scoped.example.test",
                              frontend_domain_status=Makerspace.DomainStatus.VERIFIED)
    client = APIClient()
    client.force_authenticate(account())
    response = client.post(reverse("auth-organizations-self-service"),
                           {"name": "Private", "slug": "private"}, format="json",
                           HTTP_ORIGIN="https://scoped.example.test")
    assert response.status_code == 403
    assert not Organization.objects.exists()


@pytest.mark.django_db(transaction=True)
def test_concurrent_creation_serializes_daily_quota(settings):
    settings.ORGANIZATION_SELF_CREATION_ENABLED = True
    settings.ORGANIZATION_SELF_CREATION_MAX_PER_DAY = 1
    actor = account()
    start = Barrier(2)

    def attempt(index):
        close_old_connections()
        try:
            current = User.objects.get(pk=actor.pk)
            start.wait(timeout=10)
            try:
                create_self_service(current, name=f"Org {index}", slug=f"org-{index}")
                return "created"
            except OrganizationConflict:
                return "limited"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, [1, 2]))
    assert sorted(results) == ["created", "limited"]
    assert Organization.objects.filter(created_by=actor).count() == 1


@pytest.mark.parametrize("values", [
    {"name": "x" * 201}, {"slug": "invalid slug"},
    {"website": "javascript:alert(1)"}, {"description": "x" * 10001},
])
def test_service_revalidates_boundary_without_http(settings, values):
    from rest_framework.exceptions import ValidationError
    settings.ORGANIZATION_SELF_CREATION_ENABLED = True
    with pytest.raises(ValidationError):
        create_self_service(account(), **{"name": "Private", "slug": "private", **values})
    assert not Organization.objects.exists()


def test_creation_and_initial_governance_roll_back_if_audit_fails(settings, monkeypatch):
    settings.ORGANIZATION_SELF_CREATION_ENABLED = True
    actor = account()
    def fail(*args, **kwargs):
        raise RuntimeError("audit unavailable")
    monkeypatch.setattr("apps.organizations.services_self_service.audit.record", fail)
    with pytest.raises(RuntimeError):
        create_self_service(actor, name="Private", slug="private")
    assert not Organization.objects.exists()
    assert not OrganizationMembership.objects.filter(user=actor).exists()


def test_creation_policy_has_a_per_account_attempt_throttle(settings):
    settings.ORGANIZATION_SELF_CREATION_ENABLED = True
    client = APIClient()
    client.force_authenticate(account())
    url = reverse("auth-organizations-self-service")
    for _ in range(10):
        assert client.get(url).status_code == 200
    assert client.get(url).status_code == 429
