"""Route branches: saved preferences cannot enable a disabled channel or digest policy."""
from uuid import uuid4

import pytest

from apps.integrations.models import NotificationPreference
from apps.machines.models import MachineType
from apps.notifications.models_inbox import MemberNotificationPreference, NotificationInboxRow
from tests.notifications.routes_support_cx11b_g6 import cycle, hidden, send, world

pytestmark = [pytest.mark.django_db, pytest.mark.area_notifications]
CHANNELS = [("email", "email"), ("in_app", "notifications.member_inbox"),
            ("native_push", "mobile.push"), ("native_push", "mobile"), ("sms", "sms"), ("whatsapp", "whatsapp")]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("channel,key", CHANNELS)
@pytest.mark.parametrize("method", ["get", "patch"])
def test_preference_route_channel_dependency_is_independent_and_saved_choice_retained(channel, key, method, native):
    space, actor, client, stranger, foreign = world(native)
    NotificationPreference.objects.create(makerspace=space, feature="hardware_requests", channel=channel, enabled=True)
    row = MemberNotificationPreference.objects.create(makerspace=space, user=actor,
        feature="hardware_requests", channel=channel, enabled=False)
    url = f"/api/v1/notifications/preferences/{space.pk}"
    body = {"feature": "hardware_requests", "channel": channel, "enabled": True}
    def cell(response):
        cells = [c for c in response.data["cells"] if (c["feature"], c["channel"]) == ("hardware_requests", channel)]
        assert len(cells) == 1
        return cells[0]
    def check(response):
        row.refresh_from_db()
        assert cell(response)["available"] is True
        assert cell(response)["enabled"] is (method == "patch")
        assert row.enabled is (method == "patch")
    def off_check(response):
        row.refresh_from_db()
        assert row.enabled is False
        if method == "get":
            assert cell(response)["available"] is False
            assert cell(response)["enabled"] is False
        else:
            assert set(response.data) == {"channel"}
            assert response.data["channel"].code == "invalid"
    cycle(space, key, lambda: send(client, method, url, body), check,
          off=(200 if method == "get" else 400, None), off_check=off_check,
          actions=("notification.preference_updated",) if method == "patch" else (),
          probes=[hidden(lambda: send(foreign, method, url, body), native_staff=native)])


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
def test_digest_preference_refuses_disabled_digest_without_replacing_saved_choice(native):
    space, actor, client, stranger, foreign = world(native)
    NotificationPreference.objects.create(makerspace=space, feature="hardware_requests", channel="email", enabled=True)
    row = MemberNotificationPreference.objects.create(makerspace=space, user=actor,
        feature="hardware_requests", channel="email", enabled=True, daily_digest=False)
    url = f"/api/v1/notifications/preferences/{space.pk}"
    body = {"feature": "hardware_requests", "channel": "email", "enabled": True, "daily_digest": True}
    def check(response):
        row.refresh_from_db()
        assert row.daily_digest is True and row.enabled is True
        cells = [c for c in response.data["cells"] if (c["feature"], c["channel"]) == ("hardware_requests", "email")]
        assert len(cells) == 1 and cells[0]["daily_digest"] is True
    def off_check(response):
        assert set(response.data) == {"daily_digest"}
        assert response.data["daily_digest"].code == "invalid"
    cycle(space, "notifications.digests", lambda: send(client, "patch", url, body), check,
          off=(400, None), off_check=off_check, actions=("notification.preference_updated",),
          probes=[hidden(lambda: send(foreign, "patch", url, body), native_staff=native)])


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["notifications", "notifications.member_inbox", "member_accounts", "membership", "membership.broadcasts"])
def test_member_announcement_feed_has_personal_inbox_dependency(key, native):
    space, actor, client, stranger, foreign = world(native)
    row = NotificationInboxRow.objects.create(makerspace=space, user=actor, feature="members", event="broadcast",
        event_key=uuid4(), audience="member", title="G6 member announcement")
    url = f"/api/v1/notifications/announcements/{space.pk}"
    def check(response):
        assert response.data["count"] == 1
        assert [(r["id"], r["title"]) for r in response.data["results"]] == [(row.pk, "G6 member announcement")]
    cycle(space, key, lambda: client.get(url), check,
          off=(404, "feature_disabled" if "." in key else "module_disabled"), probes=[hidden(lambda: foreign.get(url), native_staff=native)])


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
def test_broadcast_options_machine_dependency_hides_only_machine_choices(native):
    space, actor, client, stranger, foreign = world(native, staff=True)
    kind = MachineType.objects.create(makerspace=space, name="G6 segment type", slug="g6-segment")
    url = f"/api/v1/notifications/broadcasts/{space.pk}"
    def check(response):
        assert [r for r in response.data["machine_types"] if r["id"] == kind.pk] == [{"id": kind.pk, "name": "G6 segment type"}]
    def off_check(response):
        assert response.data["machine_types"] == []
    cycle(space, "machines", lambda: client.get(url), check, off=(200, None), off_check=off_check,
          probes=[hidden(lambda: foreign.get(url), native_staff=native)])


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
def test_broadcast_machine_segment_saves_exact_granted_recipient_and_refuses_off(native):
    """Report-only product regression: the source adapter still accepts certification_id."""
    from apps.integrations.models_contract import NotificationEnvelope
    from apps.machines.models import MachineAccessGrant
    from apps.notifications.models_broadcasts import MemberBroadcast
    from tests.payments.account_helpers import make_payer
    space, actor, client, stranger, foreign = world(native, staff=True)
    selected = make_payer("g6-granted-" + uuid4().hex[:8], space)
    excluded = make_payer("g6-ungranted-" + uuid4().hex[:8], space)
    kind = MachineType.objects.create(makerspace=space, name="G6 segment kind", slug="g6-granted-segment")
    MachineAccessGrant.objects.create(makerspace=space, member=selected, machine_type=kind, granted_by=actor)
    url = f"/api/v1/notifications/broadcasts/{space.pk}"
    body = {"title": "G6 granted audience", "body": "An access-granted update", "machine_type_id": kind.pk}
    def check(response):
        saved = MemberBroadcast.objects.get(pk=response.data["broadcast"]["id"])
        assert (saved.title, saved.body, saved.makerspace_id) == (body["title"], body["body"], space.pk)
        assert response.data["recipients"] == 1
        rows = NotificationEnvelope.objects.filter(source_kind="membership.broadcast", source_id=str(saved.pk))
        assert list(rows.values_list("recipient_id", flat=True)) == [selected.pk]
        assert not rows.filter(recipient=excluded).exists()
        assert rows.get().context["segment"] == {"machine_type_id": kind.pk}
    def off_check(response):
        assert set(response.data) == {"machine_type_id"}
        assert response.data["machine_type_id"].code == "invalid"
    cycle(space, "machines", lambda: send(client, "post", url, body), check, on=(201, None),
          off=(400, None), off_check=off_check, actions=("notification.broadcast_created",),
          probes=[hidden(lambda: send(foreign, "post", url, body), native_staff=native)])
