"""SPA organization-link writes require proof from the acting browser session."""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts import reauthentication
from apps.accounts.models import User
from apps.accounts.models_reauthentication import ReauthenticationSession
from apps.audit.models import AuditLog
from apps.makerspaces.models import Makerspace
from apps.organizations.models import Organization, OrganizationMakerspace
from tests.accounts.test_reauthentication import PASSWORD, request

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def platform_origin(settings):
    settings.PLATFORM_STAFF_ORIGINS = ["http://localhost:5000"]


@pytest.fixture
def link_editor():
    root = User.objects.create_superuser(username="api-link-reauth", password=PASSWORD)
    organization = Organization.objects.create(name="Protected links", slug="api-protected-links")
    space = Makerspace.objects.create(name="Protected venue", slug="api-protected-venue")
    return root, organization, space


@pytest.mark.parametrize("operation", ["add", "change", "delete"])
@pytest.mark.parametrize("proof", ["missing", "expired", "other_session", "recent"])
def test_link_api_writes_require_recent_session_proof(link_editor, operation, proof):
    root, organization, space = link_editor
    row = None
    if operation != "add":
        row = OrganizationMakerspace.objects.create(
            organization=organization, makerspace=space, relationship="affiliate")
    req = request(root)
    if proof != "missing":
        verified_request = request(root) if proof == "other_session" else req
        reauthentication.verify(verified_request, password=PASSWORD)
        if proof == "expired":
            ReauthenticationSession.objects.filter(user=root).update(
                auth_time=timezone.now() - timedelta(minutes=11))
    client = APIClient()
    client.credentials(HTTP_ORIGIN="http://localhost:5000")
    client.force_authenticate(root, token=req.auth)
    url = f"/api/v1/admin/organizations/{organization.pk}/makerspaces/"

    # Read access does not require step-up, even when a mutation would be refused.
    assert client.get(url).status_code == 200
    if operation == "delete":
        response = client.delete(f"{url}{space.pk}/")
    else:
        response = client.post(url, {"makerspace_id": space.pk, "relationship": "owner"}, format="json")

    links = OrganizationMakerspace.objects.filter(organization=organization, makerspace=space)
    audits = AuditLog.objects.filter(actor=root, action__startswith="organization.link_")
    if proof != "recent":
        assert response.status_code == 403
        assert response.data["code"] == "recent_reauth_required"
        if row:
            row.refresh_from_db()
            assert row.relationship == "affiliate"
        else:
            assert not links.exists()
        assert not audits.exists()
        return

    assert response.status_code == (204 if operation == "delete" else 200), response.data
    if operation == "delete":
        assert not links.exists()
    else:
        assert links.get().relationship == "owner"
    action = {"add": "created", "change": "updated", "delete": "deleted"}[operation]
    assert audits.get().action == f"organization.link_{action}"


def test_recent_proof_does_not_allow_non_superadmin_to_link(link_editor):
    _, organization, space = link_editor
    actor = User.objects.create_user(username="ordinary-link-editor", password=PASSWORD)
    req = request(actor)
    reauthentication.verify(req, password=PASSWORD)
    client = APIClient()
    client.credentials(HTTP_ORIGIN="http://localhost:5000")
    client.force_authenticate(actor, token=req.auth)
    url = f"/api/v1/admin/organizations/{organization.pk}/makerspaces/"
    assert client.post(url, {"makerspace_id": space.pk, "relationship": "owner"}, format="json").status_code == 403
    assert not OrganizationMakerspace.objects.exists()
    assert not AuditLog.objects.filter(action__startswith="organization.link_").exists()
