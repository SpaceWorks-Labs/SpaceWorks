"""#115: the superadmin works inside any space through its Space-Manager routes."""

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.pii_seam import MASK
from apps.audit.models import AuditLog
from apps.integrations.models import EmailLog
from apps.makerspaces.admin_console_links import CONSOLE_TABS, MakerspaceConsoleLinksAdminMixin, console_url
from apps.makerspaces.models import Makerspace
from tests.account_split.p1_helpers import staff
from tests.accounts.reauth_helpers import force_recent_authenticate
from .superadmin_parity_helpers import PLATFORM_ORIGIN, bearer

pytestmark = pytest.mark.django_db


@pytest.fixture
def world(settings):
    settings.PLATFORM_STAFF_ORIGINS = [PLATFORM_ORIGIN]
    settings.PUBLIC_APP_BASE_URL = "https://app.example.test"
    space = Makerspace.objects.create(name="Lab D", slug="lab-d")
    manager = staff(space, username="lab-d-sm", role="space_manager")[0]
    platform = User.objects.create_superuser("lab-d-platform", email="root@example.test")
    return space, manager, platform


def test_platform_surface_opens_tenant_routes_but_not_member_or_auth_routes(world):
    space, _manager, platform = world
    client = bearer(platform, origin=PLATFORM_ORIGIN)
    assert client.get(f"/api/v1/admin/makerspace/{space.pk}/inventory").status_code == 200
    assert client.get("/api/v1/memberships/me").status_code == 403
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert "manage_makerspace" in me.json()["superadmin_actions"]


def test_auth_payload_has_no_superadmin_actions_for_staff(world):
    _space, manager, _platform = world
    assert bearer(manager).get("/api/v1/auth/me").json()["superadmin_actions"] == []


def test_space_email_logs_are_masked_for_the_superadmin_only(world):
    space, manager, platform = world
    EmailLog.objects.create(makerspace=space, to_email="person@example.test", subject="Hello Ada", status="sent")
    url = f"/api/v1/admin/makerspace/{space.pk}/email-logs"
    row = bearer(manager).get(url).json()["results"][0]
    assert row["to_email"] == "person@example.test"
    response = bearer(platform, origin=PLATFORM_ORIGIN).get(url)
    row = response.json()["results"][0]
    assert response.status_code == 200 and response["X-PII-Masked"] == "1"
    assert row["to_email"] == MASK and row["subject"] == MASK
    assert row["status"] == "sent"


def test_superadmin_edits_space_email_template_audited_in_that_space(world):
    space, _manager, platform = world
    client = bearer(platform, origin=PLATFORM_ORIGIN)
    url = f"/api/v1/admin/makerspace/{space.pk}/email-templates/hardware/requester/request_received"
    response = client.patch(url, {"subject": "Hi {{ request.id }}", "text_body": "Body", "html_body": "<p>x</p>",
                                  "is_active": True}, format="json")
    assert response.status_code == 200, response.content
    row = AuditLog.objects.get(action="email_template.updated")
    assert row.makerspace_id == space.pk and row.actor_id == platform.pk


def test_superadmin_edits_space_sender_with_reauth_and_audit(world, monkeypatch):
    space, _manager, platform = world
    monkeypatch.setattr("apps.integrations.smtp_validation.socket.getaddrinfo",
                        lambda host, port, type=None: [(None, None, None, None, ("8.8.8.8", port))])
    client = APIClient()
    force_recent_authenticate(client, user=platform)
    response = client.patch(f"/api/v1/admin/makerspace/{space.pk}/api-settings", {
        "smtp_host": "smtp.example.com", "smtp_port": 2525, "smtp_username": "mailer",
        "smtp_password": "secret", "smtp_use_tls": False, "smtp_from_email": "lab@example.com",
    }, format="json")
    assert response.status_code == 200, response.content
    space.refresh_from_db()
    assert space.smtp_from_email == "lab@example.com"
    assert AuditLog.objects.filter(action="api_integration.updated", makerspace=space, actor=platform).exists()


def test_superadmin_sends_a_space_test_email_to_themselves(world):
    space, _manager, platform = world
    response = bearer(platform, origin=PLATFORM_ORIGIN).post(
        f"/api/v1/integrations/makerspace/{space.pk}/delivery-test", {}, format="json")
    assert response.status_code == 200, response.content
    assert response.json()["kind"] == "email"
    assert EmailLog.objects.get(pk=response.json()["id"]).makerspace_id == space.pk
    assert AuditLog.objects.filter(action="notification.test_sent", makerspace=space, actor=platform).exists()


def test_masked_values_are_never_written_back(world):
    space, _manager, platform = world
    response = bearer(platform, origin=PLATFORM_ORIGIN).patch(
        f"/api/v1/admin/makerspace/{space.pk}/email-templates/hardware/requester/request_received",
        {"subject": MASK, "text_body": "x", "html_body": "<p>x</p>", "is_active": True}, format="json")
    assert response.status_code == 400
    assert "pii_access_required" in response.content.decode()


def test_deployment_aggregates_open_to_the_platform_account_only(world):
    _space, manager, platform = world
    client = bearer(platform, origin=PLATFORM_ORIGIN)
    assert client.get("/api/v1/admin/reports/catalog").status_code == 200
    assert client.get("/api/v1/admin/analytics/summary").status_code == 200
    assert bearer(manager).get("/api/v1/admin/analytics/summary").status_code == 403


def test_superadmin_edits_the_space_public_page_but_not_an_organization_page(world):
    space, _manager, platform = world
    client = bearer(platform, origin=PLATFORM_ORIGIN)
    assert client.get(f"/api/v1/admin/makerspaces/{space.pk}/public-page/").status_code == 200
    from apps.makerspaces.public_page_authority import reject_platform
    from rest_framework.exceptions import PermissionDenied
    reject_platform(platform, tenant=True)
    with pytest.raises(PermissionDenied):
        reject_platform(platform)


def test_control_page_links_each_console_tab_on_that_space(world):
    space, _manager, _platform = world
    html = str(MakerspaceConsoleLinksAdminMixin().console_links(space))
    for path, label in CONSOLE_TABS:
        assert console_url(space, path) in html.replace("&amp;", "&") and label in html
    assert console_url(space, "reports") == "https://app.example.test/admin/reports?context=platform&space=lab-d"
