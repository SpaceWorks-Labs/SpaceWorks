"""Organization links extend authority and require the control session's own proof."""

from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from django.contrib import admin
from django.test import RequestFactory
from django.urls import resolve, reverse
from django.utils import timezone

from apps.accounts import reauthentication
from apps.accounts.mfa_crypto import totp
from apps.accounts.models import User
from apps.accounts.models_mfa import UserMFA
from apps.accounts.models_reauthentication import ReauthenticationSession
from apps.accounts.reauthentication_control import sensitive_control_request
from apps.audit.models import AuditLog
from apps.makerspaces.models import Makerspace
from apps.makerspaces.secrets import decrypt_value
from apps.organizations.models import Organization, OrganizationMakerspace
from tests.accounts.mfa_helpers import force_mfa_login

pytestmark = pytest.mark.django_db
PASSWORD = "Control link verification 492!"


@pytest.fixture
def link_editor(client):
    root = User.objects.create_superuser(username="control-link-reauth", password=PASSWORD)
    force_mfa_login(client, root)
    organization = Organization.objects.create(name="Protected links", slug="protected-links")
    space = Makerspace.objects.create(name="Protected venue", slug="protected-venue")
    return client, root, organization, space


def verify_control(client, root):
    request = RequestFactory().post("/mfa/reauth/")
    request.user, request.session = root, client.session
    mfa = UserMFA.objects.get(user=root)
    code = totp(decrypt_value(mfa.secret), int(timezone.now().timestamp() // 30))
    reauthentication.verify(request, password=PASSWORD, code=code)


@pytest.mark.parametrize("operation", ["add", "change", "delete", "bulk_delete"])
@pytest.mark.parametrize("proof", ["missing", "expired", "recent"])
def test_link_admin_posts_require_recent_control_proof(link_editor, operation, proof):
    client, root, organization, space = link_editor
    row = None
    if operation != "add":
        row = OrganizationMakerspace.objects.create(
            organization=organization, makerspace=space, relationship="affiliate")
    if proof != "missing":
        verify_control(client, root)
        if proof == "expired":
            ReauthenticationSession.objects.filter(user=root).update(
                auth_time=timezone.now() - timedelta(minutes=11))

    if operation == "bulk_delete":
        url = reverse("admin:organizations_organizationmakerspace_changelist")
        payload = {"action": "delete_selected", "_selected_action": [str(row.pk)], "post": "yes"}
    else:
        url = reverse(f"admin:organizations_organizationmakerspace_{operation}",
                      args=[row.pk] if row else None)
        payload = {"post": "yes"} if operation == "delete" else {
            "organization": organization.pk, "makerspace": space.pk, "relationship": "owner"}

    # Reading the forms/list is still allowed with ordinary control MFA.
    assert sensitive_control_request(RequestFactory().post(url, payload), resolve(url).func)
    assert client.get(url).status_code == 200
    response = client.post(url, payload)
    assert response.status_code == 302
    if proof != "recent":
        destination = urlsplit(response.url)
        assert destination.path == "/mfa/reauth/"
        assert parse_qs(destination.query) == {"next": [url]}
        if row:
            row.refresh_from_db()
            assert row.relationship == "affiliate"
        else:
            assert not OrganizationMakerspace.objects.exists()
        assert not AuditLog.objects.filter(action__startswith="organization.link_").exists()
        return

    assert not response.url.startswith("/mfa/reauth/")
    if operation in {"delete", "bulk_delete"}:
        assert not OrganizationMakerspace.objects.exists()
        action = "organization.link_deleted"
    else:
        saved = OrganizationMakerspace.objects.get(organization=organization, makerspace=space)
        assert saved.relationship == "owner"
        action = "organization.link_created" if operation == "add" else "organization.link_updated"
    assert AuditLog.objects.filter(action=action, actor=root, makerspace=space).count() == 1


@pytest.mark.parametrize("method", ["changeform_view", "delete_view", "changelist_view"])
def test_link_admin_mixin_also_protects_views_without_middleware(link_editor, method):
    client, root, _, _ = link_editor
    request = RequestFactory().post("/control/organizations/organizationmakerspace/")
    request.user, request.session = root, client.session
    model_admin = admin.site._registry[OrganizationMakerspace]
    args = ("1",) if method == "delete_view" else ()
    response = getattr(model_admin, method)(request, *args)
    assert response.status_code == 302
    assert response.url.startswith("/mfa/reauth/")
