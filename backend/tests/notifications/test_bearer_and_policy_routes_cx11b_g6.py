"""Signed unsubscribe is bearer authority; inbox visibility is a fallback policy."""
from datetime import timedelta
from uuid import uuid4
from urllib.parse import quote

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.integrations.email_preferences import unsubscribe_token
from apps.notifications.models_inbox import MemberNotificationPreference, NotificationInboxRow
from tests.notifications.routes_support_cx11b_g6 import cycle, send, world

pytestmark = [pytest.mark.django_db, pytest.mark.area_notifications]


@pytest.mark.parametrize("key", ["notifications", "notifications.member_preferences"])
@pytest.mark.parametrize("method", ["get", "post"])
def test_unsubscribe_signed_bearer_and_scanner_safe_get(method, key, settings):
    settings.PUBLIC_APP_BASE_URL = "https://g6.example.test"
    space, actor, _client, stranger, _foreign = world(False)
    client = APIClient()
    token = unsubscribe_token(space.pk, actor.pk, "hardware_requests")
    url = f"/api/v1/notifications/unsubscribe/{token}"
    row = MemberNotificationPreference.objects.create(makerspace=space, user=actor,
        feature="hardware_requests", channel="email", enabled=True)
    body = {"List-Unsubscribe": "One-Click"}
    def check(response):
        row.refresh_from_db()
        assert row.enabled is (method == "get")
        if method == "get":
            assert response["Location"] == f"https://g6.example.test/unsubscribe/{quote(token, safe='')}"
        else:
            assert MemberNotificationPreference.objects.get(pk=row.pk).user_id == actor.pk
            assert not MemberNotificationPreference.objects.filter(user=stranger).exists()
    # A signature substitutes for standing (views_preferences); GET only verifies/redirects.
    cycle(space, key, lambda: send(client, method, url, body), check,
          on=(302 if method == "get" else 200, None),
          off=(302, None) if method == "get" else (404, "module_disabled" if key == "notifications" else "feature_disabled"),
          off_check=check if method == "get" else None,
          actions=() if method == "get" else ("notification.unsubscribed",))
    bad = send(client, method, url + "tampered", body)
    # The HTML GET has no JSON error vocabulary; field-keyed POST errors retain DRF's field code.
    assert bad.status_code == 400
    if method == "get":
        assert bad["Content-Type"].startswith("text/html")
    else:
        assert set(bad.data) == {"token"}
        assert bad.data["token"].code == "invalid"


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("operation", ["list", "count"])
def test_snooze_visibility_policy_keeps_hidden_columns_and_restores_projection(operation, native):
    space, actor, client, stranger, foreign = world(native)
    row = NotificationInboxRow.objects.create(makerspace=space, user=actor, feature="hardware_requests",
        event="issued", event_key=uuid4(), audience="member", title="Snoozed retained notice",
        snoozed_until=timezone.now() + timedelta(hours=2))
    url = f"/api/v1/notifications/inbox/{space.pk}" + ("/unread-count" if operation == "count" else "")
    def check(response):
        assert response.data["count"] == 0
        if operation == "list":
            assert response.data["results"] == []
    def off_check(response):
        assert response.data["count"] == 1
        if operation == "list":
            assert [(r["id"], r["title"]) for r in response.data["results"]] == [(row.pk, "Snoozed retained notice")]
    from tests.notifications.routes_support_cx11b_g6 import hidden
    cycle(space, "notifications.inbox_snooze", lambda: client.get(url), check,
          off=(200, None), off_check=off_check, probes=[hidden(lambda: foreign.get(url), native_staff=native)])
