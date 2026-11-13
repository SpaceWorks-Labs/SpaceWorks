import re
from urllib.parse import parse_qs, urlsplit

import pytest
from django.contrib import admin
from django.contrib.messages import get_messages
from django.core import mail
from django.test import Client, RequestFactory
from django.urls import resolve, reverse

from apps.accounts.models_reauthentication import ReauthenticationSession
from apps.audit.models import AuditLog
from apps.hosting_requests import prefill
from apps.hosting_requests.admin import HostingRequestAdmin
from apps.hosting_requests.models import HostingRequest
from apps.makerspaces.models import Makerspace
from apps.organizations.models import Organization, OrganizationMakerspace
from config.unfold import UNFOLD
from tests.hosting_requests.helpers import invited_row, owned_space, public_row
from tests.makerspaces.test_control_makerspace_admin import control_client, form_payload

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("managed")]
CHANGELIST = "admin:hosting_requests_hostingrequest_changelist"


def sidebar_item():
    return next(
        item for group in UNFOLD["SIDEBAR"]["navigation"] for item in group["items"]
        if item and item["route"] == CHANGELIST
    )


def test_superuser_sees_changelist_and_sidebar_entry(monkeypatch):
    monkeypatch.setenv("PLATFORM_DOMAIN_SUFFIX", ".space-works.test")
    public_row()
    client = control_client()
    response = client.get(reverse(CHANGELIST))
    assert response.status_code == 200 and b"Row Space" in response.content
    request = RequestFactory().get("/control/")
    request.user = response.wsgi_request.user
    assert sidebar_item()["permission"](request) is True
    monkeypatch.setenv("PLATFORM_DOMAIN_SUFFIX", "")
    assert sidebar_item()["permission"](request) is False


def test_non_superuser_cannot_open_the_changelist():
    from tests.hosting_requests.helpers import member

    client = Client(HTTP_HOST="localhost")
    client.force_login(member("plain-member"))
    assert client.get(reverse(CHANGELIST)).status_code in (302, 403)


def test_accept_and_reject_route_through_the_workflow(django_capture_on_commit_callbacks):
    accepted, _ = public_row()
    rejected, _ = public_row(applicant_email="other@example.test")
    client = control_client()
    url = reverse(CHANGELIST)
    confirm = client.post(url, {"action": "accept_selected", "_selected_action": [accepted.pk]})
    assert confirm.status_code == 200 and b"confirm_decision" in confirm.content
    with django_capture_on_commit_callbacks(execute=True):
        client.post(url, {"action": "accept_selected", "_selected_action": [accepted.pk], "confirm_decision": "1"})
    accepted.refresh_from_db()
    assert accepted.status == "accepted"
    assert mail.outbox[-1].to == ["ada@example.test"] and "accepted" in mail.outbox[-1].subject

    page = client.post(url, {"action": "reject_selected", "_selected_action": [rejected.pk]})
    assert "do not include personal details" in page.content.decode()
    client.post(url, {"action": "reject_selected", "_selected_action": [rejected.pk],
                      "confirm_decision": "1", "rejection_reason": ""})
    rejected.refresh_from_db()
    assert rejected.status == "submitted"
    with django_capture_on_commit_callbacks(execute=True):
        client.post(url, {"action": "reject_selected", "_selected_action": [rejected.pk],
                          "confirm_decision": "1", "rejection_reason": "We only host in two regions."})
    rejected.refresh_from_db()
    assert rejected.status == "rejected"
    assert "We only host in two regions." in mail.outbox[-1].body
    assert AuditLog.objects.filter(action__in=["hosting_request.accepted", "hosting_request.rejected"]).count() == 2


def query(row):
    return parse_qs(urlsplit(prefill.add_url(row)).query)


def test_add_url_encodes_the_owner_choice():
    _space, organization = owned_space("prefill-owner", org_name="Prefill Org")
    join, _ = invited_row(organization=organization, status="accepted", decided_at="2026-10-01T00:00:00Z",
                          organization_choice="join", location="North Hall")
    assert query(join)["owner_organization"] == [str(organization.pk)]
    assert "new_organization_name" not in query(join)
    own, _ = public_row(status="accepted", new_organization_name="My Collective")
    assert query(own)["new_organization_name"] == ["My Collective"]
    assert query(own)["slug"] == ["row-space"] and query(own)["hosting_request"] == [str(own.pk)]
    Organization.objects.filter(pk=organization.pk).update(is_active=False)
    join.refresh_from_db()
    assert "owner_organization" not in query(join) and "new_organization_name" not in query(join)
    assert "no longer active" in prefill.owner_choice_summary(join)


def test_custom_url_resolves_to_the_create_makerspace_view():
    match = resolve(reverse("admin:hosting_requests_hostingrequest_create_makerspace", args=[7]))
    assert match.func.__name__ == "create_makerspace_view"


def test_create_makerspace_requires_recent_reauth_and_an_accepted_row():
    row, _ = public_row(status="accepted")
    client = control_client()
    url = reverse("admin:hosting_requests_hostingrequest_create_makerspace", args=[row.pk])
    fresh = client.get(url)
    assert fresh.status_code == 302 and fresh.url == prefill.add_url(row)
    ReauthenticationSession.objects.all().delete()
    stale = client.get(url)
    assert stale.status_code == 302 and stale.url.startswith("/mfa/reauth/?next=")
    assert row.pk and f"%2F{row.pk}%2Fcreate-makerspace%2F" in stale.url
    pending, _ = public_row()
    refused = client.get(reverse("admin:hosting_requests_hostingrequest_create_makerspace", args=[pending.pk]))
    assert refused.status_code == 302 and "makerspace/add" not in refused.url


def test_round_trip_creates_with_own_organization_for_a_join_request_and_links_once():
    _space, organization = owned_space("round-trip-owner", org_name="Round Trip Org")
    row, _ = invited_row(organization=organization, status="accepted", decided_at="2026-10-01T00:00:00Z",
                         space_name="Round Trip Lab", location="East Wing")
    client = control_client()
    add = prefill.add_url(row)
    page = client.get(add)
    assert page.status_code == 200
    hidden = re.search(r'<input[^>]*name="hosting_request"[^>]*>', page.content.decode())
    assert hidden and 'type="hidden"' in hidden.group(0) and f'value="{row.pk}"' in hidden.group(0)

    candidate = Makerspace(name="Round Trip Lab", slug="round-trip-lab", location="East Wing", public_code="RTLB")
    # #49: the superadmin may give a "join" request its own organization instead.
    response = client.post(add, form_payload(candidate, new_organization_name="Round Trip Own Org",
                                             hosting_request=str(row.pk)))
    assert response.status_code == 302, getattr(response, "context_data", None)
    created = Makerspace.objects.get(slug="round-trip-lab")
    row.refresh_from_db()
    assert row.created_makerspace_id == created.pk
    assert OrganizationMakerspace.objects.get(makerspace=created).organization.name == "Round Trip Own Org"
    assert AuditLog.objects.filter(action="hosting_request.makerspace_linked").count() == 1

    again = Makerspace(name="Second Lab", slug="second-lab", public_code="SCND")
    second = client.post(add, form_payload(again, new_organization_name="Another Org",
                                           hosting_request=str(row.pk)))
    assert second.status_code == 302 and second.url == add
    notes = [str(message) for message in get_messages(second.wsgi_request)]
    assert any(note.startswith("Makerspace was not created") for note in notes)
    assert not Makerspace.objects.filter(slug="second-lab").exists()


def test_admin_is_read_only_and_hidden_on_self_host(settings):
    from tests.hosting_requests.helpers import superadmin

    request = RequestFactory().get("/control/")
    request.user = superadmin("readonly-root")
    model_admin = admin.site._registry[HostingRequest]
    assert isinstance(model_admin, HostingRequestAdmin)
    assert model_admin.has_view_permission(request) is True
    assert model_admin.has_add_permission(request) is False
    assert model_admin.has_change_permission(request) is False
    assert model_admin.has_delete_permission(request) is False
    settings.PLATFORM_DOMAIN_SUFFIX = ""
    assert model_admin.has_module_permission(request) is False
    assert model_admin.has_view_permission(request) is False
