"""481/494: makerspace-addressed staff commands conceal foreign tenant standing."""
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.makerspaces.models import MembershipPlan
from apps.notifications.models import Notification
from apps.notifications.models_broadcasts import MemberBroadcast
from apps.notifications.models_inbox import NotificationInboxRow
from tests.notifications.routes_support_cx11b_g6 import cycle, hidden, send, world
from tests.payments.account_helpers import make_payer

pytestmark = [pytest.mark.django_db, pytest.mark.area_notifications]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("operation", ["list", "count", "read", "read-all"])
def test_legacy_feed_exact_row_and_read_audit_restore(operation, native, monkeypatch):
    space, actor, client, stranger, foreign = world(native, staff=True)
    now = timezone.now()
    monkeypatch.setattr(timezone, "now", lambda: now)
    row = Notification.objects.create(makerspace=space, title="G6 legacy notice", body="Retained body")
    tail = {"list": "", "count": "/unread-count", "read": f"/{row.pk}/read", "read-all": "/read-all"}[operation]
    url = f"/api/v1/notifications/makerspace/{space.pk}" + tail
    method = "get" if operation in {"list", "count"} else "post"
    def check(response):
        row.refresh_from_db()
        if operation == "list":
            assert response.data["count"] == 1
            assert [(r["id"], r["title"], r["body"]) for r in response.data["results"]] == [
                (row.pk, "G6 legacy notice", "Retained body")]
        elif operation == "count":
            assert response.data == {"count": 1}
        else:
            assert row.read_at == now
            if operation == "read-all":
                assert response.data == {"updated": 1}
            else:
                assert response.data["id"] == row.pk
    actions = () if method == "get" else ("notification.read_all" if operation == "read-all" else "notification.read",)
    cycle(space, "notifications", lambda: send(client, method, url), check,
          off=(404, "module_disabled"), actions=actions, probes=[hidden(lambda: send(foreign, method, url), native_staff=native)])


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("operation", ["options", "create", "feed"])
@pytest.mark.parametrize("key", ["member_accounts", "membership", "notifications", "membership.broadcasts"])
def test_broadcast_routes_keep_exact_source_recipient_and_announcement(operation, key, native):
    space, actor, client, stranger, foreign = world(native, staff=True)
    member = make_payer("g6-recipient-" + uuid4().hex[:8], space)
    plan = MembershipPlan.objects.create(makerspace=space, name="G6 retained plan", interval="monthly")
    row = NotificationInboxRow.objects.create(makerspace=space, user=actor, feature="members",
        event="broadcast", event_key=uuid4(), audience="staff", title="G6 announcement")
    url = f"/api/v1/notifications/{'announcements' if operation == 'feed' else 'broadcasts'}/{space.pk}"
    method = "post" if operation == "create" else "get"
    body = {"title": "G6 broadcast", "body": "Meet in the annex"}
    before = MemberBroadcast.objects.count()
    def check(response):
        if operation == "options":
            assert response.data["plans"] == [{"id": plan.pk, "name": "G6 retained plan"}]
        elif operation == "feed":
            assert response.data["count"] == 1
            assert [(r["id"], r["title"]) for r in response.data["results"]] == [(row.pk, "G6 announcement")]
        else:
            assert MemberBroadcast.objects.count() == before + 1
            saved = MemberBroadcast.objects.get(pk=response.data["broadcast"]["id"])
            assert (saved.title, saved.body, saved.created_by_id, saved.makerspace_id) == (
                "G6 broadcast", "Meet in the annex", actor.pk, space.pk)
            assert response.data["recipients"] == 1
            from apps.integrations.models_contract import NotificationEnvelope
            assert list(NotificationEnvelope.objects.filter(source_kind="membership.broadcast",
                source_id=str(saved.pk)).values_list("recipient_id", "feature", "event")) == [(member.pk, "members", "broadcast")]
            from apps.notifications.broadcasts import segment_members
            assert list(segment_members(space, {}).values_list("user_id", flat=True)) == [member.pk]
    cycle(space, key, lambda: send(client, method, url, body), check,
          on=(201 if operation == "create" else 200, None),
          off=(404, "feature_disabled" if "." in key else "module_disabled"),
          actions=("notification.broadcast_created",) if operation == "create" else (),
          probes=[hidden(lambda: send(foreign, method, url, body), native_staff=native)])
