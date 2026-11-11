import re

import pytest
from django.urls import reverse

from apps.hosting_requests.models import HostingRequest
from apps.makerspaces.models import Makerspace
from tests.hosting_requests.helpers import (
    ANSWER, OPEN, RESOLVE, SUBMIT, anonymous, client_for, payload, public_row, space,
    space_manager,
)
from tests.makerspaces.test_control_makerspace_admin import control_client, form_payload

pytestmark = pytest.mark.django_db
PUBLIC = (SUBMIT, OPEN, RESOLVE, ANSWER)


def staff_routes(makerspace):
    base = f"/api/v1/admin/makerspaces/{makerspace.pk}/hosting-invitations"
    return (("get", base), ("post", base), ("post", f"{base}/1/cancel"),
            ("get", "/api/v1/admin/organizations/1/hosting-invitations/"),
            ("post", "/api/v1/admin/organizations/1/hosting-invitations/"),
            ("post", "/api/v1/admin/organizations/1/hosting-invitations/2/cancel"))


@pytest.mark.usefixtures("self_host")
def test_every_route_404s_and_config_has_no_flag_on_self_host():
    for url in PUBLIC:
        assert anonymous().post(url, {**payload(), "token": "t" * 40}, format="json").status_code == 404, url
    makerspace = space("inert-space")
    manager = space_manager(makerspace)
    for method, url in staff_routes(makerspace):
        response = getattr(client_for(manager), method)(url, {"invitee_email": "a@example.test"}, format="json")
        assert response.status_code == 404, url
    assert "hosting_requests" not in anonymous().get("/api/v1/config").data
    assert not HostingRequest.objects.exists()


@pytest.mark.usefixtures("self_host")
def test_admin_and_add_form_ignore_hosting_requests_on_self_host():
    client = control_client()
    assert client.get(reverse("admin:hosting_requests_hostingrequest_changelist")).status_code == 403
    add = reverse("admin:makerspaces_makerspace_add")
    page = client.get(add)
    assert page.status_code == 200 and 'name="hosting_request"' not in page.content.decode()
    accepted, _ = public_row(status="accepted")
    candidate = Makerspace(name="Self Lab", slug="self-lab", public_code="SELF")
    response = client.post(add, form_payload(candidate, new_organization_name="Self Org",
                                             hosting_request=str(accepted.pk)))
    assert response.status_code == 302
    accepted.refresh_from_db()
    assert Makerspace.objects.filter(slug="self-lab").exists() and accepted.created_makerspace_id is None


def test_managed_without_mail_or_base_url_keeps_public_routes_off(settings, monkeypatch):
    settings.PLATFORM_DOMAIN_SUFFIX = ".space-works.test"
    settings.INFRA_HOSTS = {"testserver", "localhost"}
    settings.PUBLIC_APP_BASE_URL = "https://app.space-works.test"
    monkeypatch.setattr("apps.hosting_requests.availability.email_enabled", lambda: False)
    assert anonymous().post(SUBMIT, payload(), format="json").status_code == 404
    assert "hosting_requests" not in anonymous().get("/api/v1/config").data
    monkeypatch.setattr("apps.hosting_requests.availability.email_enabled", lambda: True)
    settings.PUBLIC_APP_BASE_URL = ""
    assert anonymous().post(SUBMIT, payload(), format="json").status_code == 404
    settings.PUBLIC_APP_BASE_URL = "https://app.space-works.test"
    assert anonymous().get("/api/v1/config").data["hosting_requests"] == {"enabled": True}
    assert re.match(r"^2\d\d$", str(anonymous().post(SUBMIT, payload(), format="json").status_code))
