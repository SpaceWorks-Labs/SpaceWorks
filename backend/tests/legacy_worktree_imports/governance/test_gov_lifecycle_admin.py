"""Control lifecycle actions require step-up, with no hidden-tenant inference."""

from datetime import timedelta

import pytest
from django.contrib import admin
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models_reauthentication import ReauthenticationSession
from apps.makerspaces.models import Makerspace, MakerspaceArchiveRequest
from tests.accounts.mfa_helpers import force_mfa_login
from tests.accounts.reauth_helpers import force_recent_control_login
from tests.governance.test_gov_lifecycle import platform

pytestmark = pytest.mark.django_db


def list_url():
    return reverse("admin:makerspaces_makerspace_changelist")


def fixtures():
    from apps.accounts.models import User
    actor = platform()
    space = Makerspace.objects.create(name="Hidden governance", slug="hidden-governance",
        location="SECRET-LOCATION", frontend_domain="secret.example.test")
    requester = User.objects.create_user(username="known-requester", email="PRIVATE-CONTACT@example.test",
                                         first_name="PRIVATE-FIRST-NAME")
    pending = MakerspaceArchiveRequest.objects.create(makerspace=space, requested_by=requester,
        reason="Only this reason is disclosed")
    return actor, space, pending


@pytest.mark.skip(reason="decision 110 (superadmin always on; hidden-space/slim-list premise and Makerspace.superadmin_access_enabled removed)")
def test_slim_list_and_pending_review_disclose_governance_only():
    actor, space, pending = fixtures()
    client = Client()
    force_recent_control_login(client, actor)
    response = client.get(list_url())
    body = response.content.decode()
    assert space.name in body and space.slug in body and "off" in body
    for secret in (space.location, space.frontend_domain, str(space.public_code)):
        assert secret not in body
    assert reverse("admin:makerspaces_makerspace_change", args=[space.pk]) not in body
    model_admin = admin.site._registry[Makerspace]
    assert set(model_admin.get_actions(response.wsgi_request)) == {
        "archive_makerspaces", "unarchive_makerspaces", "purge_makerspaces",
        "approve_archive_requests", "decline_archive_requests",
    }
    for action in ("approve_archive_requests", "decline_archive_requests"):
        confirmation = client.post(list_url(), {"action": action, ACTION_CHECKBOX_NAME: str(space.pk)})
        assert confirmation.status_code == 200
        content = confirmation.content.decode()
        assert str(pending.pk) in content and pending.reason in content and "known-requester" in content
        assert "PRIVATE-CONTACT" not in content and "PRIVATE-FIRST-NAME" not in content
        assert set(confirmation.context_data["requests"][0]) == {"id", "requested_at", "username", "reason"}
        assert "Unsettled-charge counts" not in content
        assert "Owned pending" not in content and "Routed pending" not in content
        assert "Total pending" not in content


@pytest.mark.skip(reason="decision 110 (superadmin always on; hidden-space/slim-list premise and Makerspace.superadmin_access_enabled removed)")
@pytest.mark.parametrize("query", [{"q": "SECRET-LOCATION"}, {"q": "secret.example.test"},
                                   {"public_inventory_enabled__exact": "1"}])
def test_hidden_rows_do_not_match_private_search_or_filters(query):
    actor, space, pending = fixtures()
    client = Client()
    force_recent_control_login(client, actor)
    assert space.name not in client.get(list_url(), query).content.decode()
    assert space.name in client.get(list_url(), {"q": space.slug}).content.decode()


@pytest.mark.skip(reason="decision 110 (superadmin always on; hidden-space/slim-list premise and Makerspace.superadmin_access_enabled removed)")
def test_crafted_private_ordering_cannot_order_hidden_rows():
    actor, first, pending = fixtures()
    second = Makerspace.objects.create(name="A hidden second", slug="hidden-second", location="ZZZ")
    client = Client()
    force_recent_control_login(client, actor)
    # List column four is location; requesting it cannot change name ordering.
    response = client.get(list_url(), {"o": "4"})
    rows = list(response.context_data["cl"].result_list)
    assert [row.pk for row in rows] == [second.pk, first.pk]


@pytest.mark.parametrize("proof", ["missing", "expired"])
@pytest.mark.parametrize("action,confirmation", [
    ("archive_makerspaces", "confirm_archive"), ("unarchive_makerspaces", ""),
    ("purge_makerspaces", "confirm_purge"), ("approve_archive_requests", "confirm_review"),
    ("decline_archive_requests", "confirm_review"),
])
@pytest.mark.parametrize("confirmed", [False, True])
def test_lifecycle_selection_and_direct_confirmation_need_recent_proof(proof, action, confirmation, confirmed):
    actor, space, pending = fixtures()
    client = Client()
    if proof == "missing":
        force_mfa_login(client, actor)
    else:
        force_recent_control_login(client, actor)
        ReauthenticationSession.objects.update(auth_time=timezone.now() - timedelta(days=1))
    data = {"action": action, ACTION_CHECKBOX_NAME: str(space.pk), "resolution_note": "Declined",
            f"slug_{space.pk}": space.slug}
    if confirmed and confirmation:
        data[confirmation] = "1"
    response = client.post(list_url(), data)
    assert response.status_code == 302 and response.url.startswith("/mfa/reauth/")
    space.refresh_from_db()
    pending.refresh_from_db()
    assert space.archived_at is None and pending.status == "pending"


@pytest.mark.parametrize("proof", ["missing", "expired"])
def test_ordinary_delete_and_request_admin_direct_confirmation_require_step_up(proof):
    actor, space, pending = fixtures()
    visible = Makerspace.objects.create(name="Visible archived", slug="visible-archived", archived_at=timezone.now())
    visible_request = MakerspaceArchiveRequest.objects.create(makerspace=visible, requested_by=actor, reason="Close")
    client = Client()
    force_mfa_login(client, actor) if proof == "missing" else force_recent_control_login(client, actor)
    if proof == "expired":
        ReauthenticationSession.objects.update(auth_time=timezone.now() - timedelta(days=1))
    response = client.post(reverse("admin:makerspaces_makerspace_delete", args=[visible.pk]), {"post": "yes"})
    assert response.status_code == 302 and response.url.startswith("/mfa/reauth/")
    for action, marker in [("approve_selected", "confirm_archive_requests"), ("decline_selected", "confirm_decline")]:
        response = client.post(reverse("admin:makerspaces_makerspacearchiverequest_changelist"),
            {"action": action, ACTION_CHECKBOX_NAME: str(visible_request.pk), marker: "1", "resolution_note": "Close"})
        assert response.status_code == 302 and response.url.startswith("/mfa/reauth/")
    assert Makerspace.objects.filter(pk=visible.pk).exists()


@pytest.mark.parametrize("approve", [False, True])
def test_recent_platform_operator_can_review_hidden_request_from_slim_list(approve, monkeypatch):
    from apps.makerspaces import archive_requests
    monkeypatch.setattr(archive_requests, "schedule_resolved", lambda pk: None)
    actor, space, pending = fixtures()
    client = Client()
    force_recent_control_login(client, actor)
    response = client.post(list_url(), {"action": "approve_archive_requests" if approve else "decline_archive_requests",
        ACTION_CHECKBOX_NAME: str(space.pk), "confirm_review": "1", "resolution_note": "Temporary closure"})
    assert response.status_code == 302
    space.refresh_from_db()
    pending.refresh_from_db()
    assert pending.status == ("approved" if approve else "declined")
    assert (space.archived_at is not None) == approve


def test_recent_platform_operator_can_archive_unarchive_and_purge_hidden_row(monkeypatch):
    from apps.makerspaces import archive_requests, lifecycle
    from apps.audit.models import AuditLog
    monkeypatch.setattr(archive_requests, "schedule_resolved", lambda pk: None)
    monkeypatch.setattr(lifecycle, "_delete_storage_keys", lambda keys: None)
    monkeypatch.setattr(lifecycle, "_delete_public_image_keys", lambda keys: None)
    actor, space, pending = fixtures()
    client = Client()
    force_recent_control_login(client, actor)
    for action, marker in [("archive_makerspaces", "confirm_archive"), ("unarchive_makerspaces", ""),
                           ("archive_makerspaces", "confirm_archive"), ("purge_makerspaces", "confirm_purge")]:
        data = {"action": action, ACTION_CHECKBOX_NAME: str(space.pk), f"slug_{space.pk}": space.slug}
        if marker:
            data[marker] = "1"
        response = client.post(list_url(), data)
        assert response.status_code == 302
        if action != "purge_makerspaces":
            space.refresh_from_db()
            assert (space.archived_at is not None) == (action == "archive_makerspaces")
    assert not Makerspace.objects.filter(pk=space.pk).exists()
    completed = AuditLog.objects.get(action="makerspace.purged")
    assert "superadmin_access_enabled" not in completed.meta
