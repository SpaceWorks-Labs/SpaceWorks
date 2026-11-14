"""525: each personal route proves its own row/effect, switch and no-standing contract."""
from datetime import timedelta
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.notifications.models_inbox import MemberNotificationPreference, NotificationInboxRow
from tests.notifications.routes_support_cx11b_g6 import cycle, hidden, send, world
from tests.notifications.test_object_switches_cx11b_p2 import personal_client
from tests.payments.account_helpers import make_payer

pytestmark = [pytest.mark.django_db, pytest.mark.area_notifications]

OPERATIONS = [
    ("list", "get", "", ()), ("families", "get", "/families", ()),
    ("count", "get", "/unread-count", ()),
    ("read-all", "post", "/read-all", ("notification.inbox_read_all",)),
    ("read", "post", "/{pk}/read", ("notification.inbox_read",)),
    ("snooze", "post", "/{pk}/snooze", ("notification.inbox_snoozed",)),
    ("archive", "post", "/{pk}/archive", ("notification.inbox_archived",)),
    ("restore", "post", "/{pk}/restore", ("notification.inbox_restored",)),
    ("preferences-get", "get", "", ()),
    ("preferences-patch", "patch", "", ("notification.preference_updated",)),
]
CASES = [(op, key, native) for op in OPERATIONS for key in (
    "notifications", "notifications.member_preferences" if op[0].startswith("preferences")
    else "notifications.member_inbox", *(["notifications.inbox_snooze"]
    if op[0] in {"snooze", "archive", "restore"} else [])) for native in (False, True)]


@pytest.mark.parametrize("op,key,native", CASES, ids=lambda value: str(value))
def test_personal_route_effect_and_standing_survive_each_independent_switch(op, key, native, monkeypatch):
    name, method, tail, actions = op
    space, person, client, stranger, foreign = world(native)
    now = timezone.now()
    monkeypatch.setattr(timezone, "now", lambda: now)
    row = NotificationInboxRow.objects.create(makerspace=space, user=person, feature="hardware_requests",
        event="issued", event_key=uuid4(), audience="member", title="G6 addressed notice", summary="Only its owner")
    if name == "restore":
        row.archived_on, row.snoozed_until = now, now + timedelta(hours=2)
        row.save(update_fields=["archived_on", "snoozed_until"])
    preference = MemberNotificationPreference.objects.create(makerspace=space, user=person,
        feature="hardware_requests", channel="email", enabled=True)
    url = f"/api/v1/notifications/inbox/{space.pk}" + tail.format(pk=row.pk)
    body = {"until": (now + timedelta(hours=2)).isoformat()} if name == "snooze" else {}
    if name.startswith("preferences"):
        url = f"/api/v1/notifications/preferences/{space.pk}"
        body = {"feature": "hardware_requests", "channel": "email", "enabled": False}
    probes = [hidden(lambda: send(foreign, method, url, body), native_staff=native)]
    if name in {"read", "snooze", "archive", "restore"}:
        peer = make_payer("g6-peer-" + uuid4().hex[:8], space)
        peer_client = personal_client(peer, space, native)
        NotificationInboxRow.objects.create(makerspace=space, user=peer, feature="hardware_requests",
            event="issued", event_key=uuid4(), audience="member", title="G6 peer's own notice")
        probes.append(hidden(lambda: send(peer_client, method, url, body)))

    def check(response):
        row.refresh_from_db()
        preference.refresh_from_db()
        if name == "list":
            assert response.data["count"] == 1
            assert [(r["id"], r["title"], r["summary"]) for r in response.data["results"]] == [
                (row.pk, "G6 addressed notice", "Only its owner")]
        elif name == "families":
            assert response.data == {"families": ["hardware_requests"]}
        elif name == "count":
            assert response.data == {"count": 1}
        elif name == "read-all":
            assert response.data == {"updated": 1}
            assert row.read_at == now
        elif name == "read":
            assert response.data["id"] == row.pk
            assert row.read_at == now
        elif name == "snooze":
            assert response.data["id"] == row.pk
            assert row.snoozed_until == now + timedelta(hours=2)
        elif name == "archive":
            assert response.data["id"] == row.pk
            assert row.archived_on == now
        elif name == "restore":
            assert response.data["id"] == row.pk
            assert (row.archived_on, row.snoozed_until) == (None, None)
        else:
            cells = [c for c in response.data["cells"] if (c["feature"], c["channel"]) == (
                "hardware_requests", "email")]
            assert len(cells) == 1
            assert cells[0]["enabled"] is (name == "preferences-get")
            assert preference.enabled is (name == "preferences-get")
    off = "module_disabled" if key == "notifications" else (
        "not_found" if key == "notifications.inbox_snooze" else "feature_disabled")
    cycle(space, key, lambda: send(client, method, url, body), check,
          off=(404, off), probes=probes, actions=actions)


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("operation", ["inbox", "preferences"])
@pytest.mark.parametrize("module", [True, False])
def test_revoked_personal_membership_keeps_decided_403_in_every_switch_state(native, operation, module):
    from apps.makerspaces.models import MakerspaceMembership
    space, actor, client, stranger, foreign = world(native)
    row = NotificationInboxRow.objects.create(makerspace=space, user=actor, feature="hardware_requests",
        event="issued", event_key=uuid4(), audience="member", title="Retained revoked member's notice")
    MakerspaceMembership.objects.filter(makerspace=space, user=actor).update(status="revoked")
    key = "notifications" if module else "notifications.member_" + ("inbox" if operation == "inbox" else "preferences")
    url = f"/api/v1/notifications/{operation}/{space.pk}"
    def check(response):
        assert response.data["code"] == "permission_denied"
        assert NotificationInboxRow.objects.get(pk=row.pk).title == "Retained revoked member's notice"
    cycle(space, key, lambda: client.get(url), check, on=(403, "permission_denied"), off=(403, "permission_denied"))
