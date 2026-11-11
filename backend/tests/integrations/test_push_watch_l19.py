"""L19 watch-friendly push (#116, #128 C-27): payload v3, category registry, safe actions."""

from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest
from rest_framework.test import APIClient

from apps.integrations import push_categories as reg
from apps.integrations.notification_catalog import FEATURE_EVENTS
from apps.integrations.notification_delivery import send
from apps.integrations.notification_enums import NotificationFeature
from apps.integrations.push_apns import aps_payload
from apps.integrations.push_fcm import fcm_message
from apps.integrations.push_payload import BODY_LIMIT, TITLE_LIMIT, push_data, shorten, short_body, short_title
from apps.makerspaces.capabilities import FEATURES, default_enabled_features
from apps.notifications.models_inbox import NotificationInboxRow
from tests.notifications.test_support_m1b import push_case, wire_message  # noqa: F401

pytestmark = pytest.mark.django_db
V2_KEYS = {"v", "event_id", "makerspace_id", "feature", "event", "inbox_row_id", "link"}


def _switch(space, key, on):
    features = set(space.enabled_features)
    space.enabled_features = sorted(features | {key} if on else features - {key})
    space.save(update_fields=["enabled_features"])


# --- length bounds -----------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "Your loan of the Prusa MK4 3D printer is due back tomorrow at the front desk " * 3,
    "x" * 500, "word " * 100, "  spaced\n\nout\ttext  " * 20,
])
def test_title_and_body_never_exceed_watch_limits(text):
    assert len(short_title(text)) <= TITLE_LIMIT == 40
    assert len(short_body(text)) <= BODY_LIMIT == 120
    assert "\n" not in short_body(text) and "  " not in short_body(text)


def test_short_text_is_unchanged_and_long_text_cuts_at_a_word():
    assert short_title("Booking confirmed") == "Booking confirmed"
    cut = shorten("Your booking for the laser cutter is confirmed for Friday", 40)
    assert cut == "Your booking for the laser cutter is…"  # no half word before the ellipsis
    assert shorten("a" * 80, 40) == "a" * 39 + "…"  # one long word is hard-cut


@pytest.mark.parametrize("push_case", ["fcm", "apns"], indirect=True)
def test_wire_title_and_body_are_bounded(push_case):
    case = push_case
    case.rendered["subject"] = "An unusually long subject line that keeps going and going"
    send(case.prepare().pk)
    alert, _ = wire_message(case)
    assert len(alert["title"]) <= 40 and len(alert["body"]) <= 120
    assert alert["title"].startswith("An unusually long subject")


# --- registry totality and safety -----------------------------------------------------------

def test_every_notification_feature_has_a_channel_and_every_event_resolves():
    assert set(reg.FEATURE_CHANNELS) == set(NotificationFeature.values)
    assert set(reg.FEATURE_CHANNELS.values()) <= set(reg.CHANNELS)
    for feature, events in FEATURE_EVENTS.items():
        for event in events:
            assert reg.channel_for(feature, event) in reg.CHANNELS
            assert isinstance(reg.actionable(feature, event), bool)


def test_the_no_action_set_is_exactly_the_declared_money_and_evidence_events():
    declared = {(f, e) for f, events in {**reg.MONEY_EVENTS}.items() for e in events}
    declared |= {(f, e) for f, events in reg.EVIDENCE_EVENTS.items() for e in events}
    declared |= {("payments", e) for e in FEATURE_EVENTS["payments"]}
    for feature, event in declared:
        assert event in FEATURE_EVENTS[feature], f"stale registry entry {feature}.{event}"
    none = {(f, e) for f, events in FEATURE_EVENTS.items() for e in events if not reg.actionable(f, e)}
    # The token guard is a backstop for future events; today nothing falls to it silently.
    assert none == declared


def test_categories_only_hold_safe_actions():
    assert reg.SAFE_ACTIONS == ("open", "mark_seen", "snooze")
    for actions in reg.CATEGORIES.values():
        assert actions[0] == "open" and set(actions) <= set(reg.SAFE_ACTIONS)
    banned = ("approve", "accept", "reject", "pay", "refund", "issue", "return", "handover", "evidence")
    assert not any(word in action for actions in reg.CATEGORIES.values() for action in actions for word in banned)


def test_unknown_or_future_unsafe_events_fail_closed(push_case):
    space = push_case.space
    assert reg.category_for(space, "bookings", "made_up_event", has_inbox_row=True) is None
    assert reg.category_for(space, "nonexistent", "confirmed", has_inbox_row=True) is None
    assert not reg.actionable("bookings", "refund_due")  # not catalogued AND a money token


@pytest.mark.parametrize("feature,event", sorted(
    {("payments", e) for e in FEATURE_EVENTS["payments"]}
    | {(f, e) for f, events in reg.MONEY_EVENTS.items() for e in events}
    | {(f, e) for f, events in reg.EVIDENCE_EVENTS.items() for e in events}))
def test_no_action_on_money_or_evidence_events(push_case, feature, event):
    space = push_case.space
    _switch(space, "notifications.inbox_snooze", True)
    data = push_data(event_id=uuid4(), makerspace_id=space.pk, feature=feature, event=event,
                     inbox_row_id=7, makerspace=space)
    assert "category" not in data
    if reg.is_money(feature, event):
        assert data["channel"] == "sw_money"


# --- actions, capability and v2 compatibility on the real transports ------------------------

@pytest.mark.parametrize("push_case", ["fcm", "apns"], indirect=True)
def test_mark_seen_round_trip_reads_the_inbox_row(push_case):
    case = push_case
    send(case.prepare().pk)
    _, data = wire_message(case)
    assert data["category"] == "sw.inbox" and "mark_seen" in reg.CATEGORIES[data["category"]]
    if case.device.provider == "apns":
        assert case.calls[0]["json"]["aps"]["category"] == "sw.inbox"
    client = APIClient()
    client.force_authenticate(case.user)
    response = client.post(f"/api/v1/notifications/inbox/{data['makerspace_id']}/{data['inbox_row_id']}/read")
    assert response.status_code == 200, response.content
    row = NotificationInboxRow.objects.get(pk=int(data["inbox_row_id"]))
    assert row.read_at is not None and response.json()["read_at"]


def test_snooze_is_offered_only_while_inbox_snooze_is_on(push_case):
    case = push_case
    _switch(case.space, "notifications.inbox_snooze", True)
    send(case.prepare().pk)
    _, data = wire_message(case)
    assert data["category"] == "sw.inbox.snooze"
    client = APIClient()
    client.force_authenticate(case.user)
    from datetime import timedelta
    from django.utils import timezone
    until = (timezone.now() + timedelta(hours=1)).isoformat()
    response = client.post(f"/api/v1/notifications/inbox/{case.space.pk}/{data['inbox_row_id']}/snooze",
                           {"until": until}, format="json")
    assert response.status_code == 200, response.content
    _switch(case.space, "notifications.inbox_snooze", False)
    assert push_data(event_id=uuid4(), makerspace_id=case.space.pk, feature="bookings",
                     event="confirmed", inbox_row_id=1, makerspace=case.space)["category"] == "sw.inbox"


@pytest.mark.parametrize("push_case", ["fcm", "apns"], indirect=True)
def test_capability_off_sends_no_category(push_case):
    case = push_case
    assert "mobile.watch_actions" in case.space.enabled_features
    _switch(case.space, "mobile.watch_actions", False)
    send(case.prepare().pk)
    alert, data = wire_message(case)
    assert "category" not in data and data["channel"] == "sw_bookings"
    if case.device.provider == "apns":
        assert "category" not in case.calls[0]["json"]["aps"]
    else:
        assert "click_action" not in str(case.calls[0]["json"])


@pytest.mark.parametrize("push_case", ["fcm", "apns"], indirect=True)
def test_v2_clients_are_unaffected(push_case):
    """Every v2 key keeps its name and value; v3 only adds string keys v2 apps ignore."""
    case = push_case
    send(case.prepare().pk)
    alert, data = wire_message(case)
    assert set(alert) == {"title", "body"}
    assert data["event_id"] == str(uuid5(NAMESPACE_URL, case.envelope.dedup_key))
    assert data["makerspace_id"] == str(case.space.pk)
    assert (data["feature"], data["event"]) == ("bookings", "confirmed")
    assert data["inbox_row_id"] == str(case.inbox.pk) and data["link"] == f"/m/{case.space.slug}/member"
    assert set(data) - V2_KEYS == {"channel", "category"}
    assert all(isinstance(value, str) for value in data.values()) and data["v"] == "3"
    if case.device.provider == "apns":
        assert case.calls[0]["json"]["aps"]["thread-id"] == str(case.space.pk)
    else:
        assert case.calls[0]["json"]["message"]["notification"] == alert


def test_events_get_a_subthread_and_android_a_channel_and_tag():
    data = {"makerspace_id": "12", "event_id": "abc", "channel": "sw_events", "category": "sw.open"}
    assert aps_payload("t", "b", data)["thread-id"] == "12.events"
    assert aps_payload("t", "b", {**data, "channel": "sw_loans"})["thread-id"] == "12"
    message = fcm_message("tok", "t", "b", data)
    assert message["android"] == {"notification": {"channel_id": "sw_events", "tag": "sw-abc"}}
    assert "click_action" not in str(message)
    # A v2-shaped data dict (no channel) still produces the v2 wire message.
    assert set(fcm_message("tok", "t", "b", {"makerspace_id": "1"})) == {"token", "notification", "data"}


def test_watch_actions_capability_is_default_on_under_mobile():
    definition = FEATURES["mobile.watch_actions"]
    assert definition.parent_module == "mobile" and definition.default_enabled
    assert "mobile.watch_actions" in default_enabled_features()


def test_backfill_enables_watch_actions_where_push_is_on(push_case):
    import importlib

    from django.apps import apps

    migration = importlib.import_module("apps.integrations.migrations.0050_watch_actions_default_on")
    on, off = push_case.space, None
    from tests.return_helpers import make_space
    off = make_space("l19-push-off")
    _switch(on, "mobile.watch_actions", False)
    off.enabled_features = sorted(set(off.enabled_features) - {"mobile.push", "mobile.watch_actions"})
    off.save(update_fields=["enabled_features"])
    migration.enable(apps, None)
    on.refresh_from_db(), off.refresh_from_db()
    assert "mobile.watch_actions" in on.enabled_features
    assert "mobile.watch_actions" not in off.enabled_features
    migration.disable(apps, None)
    on.refresh_from_db()
    assert "mobile.watch_actions" not in on.enabled_features
