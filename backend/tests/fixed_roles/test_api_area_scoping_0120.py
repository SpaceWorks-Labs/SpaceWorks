"""API-level area scoping, release 0.12.0 (owner: "each role sees only what they manage").

One world, every built-in role plus the people around them, calling the key staff list
surfaces: the dashboard, the legacy notification feed, global search and event related
facts. Out-of-area rows must be absent and out-of-area objects refused at the API, not
merely hidden by the console. The fix-specific checks live in
``test_api_area_scoping_0120_fixes.py``.
"""
import json
from types import SimpleNamespace

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.events.models import Event
from apps.inventory.models import InventoryProduct
from apps.machines.models import MachineType
from apps.makerspaces.models import Makerspace
from apps.notifications.models import Notification
from apps.operations import live
from apps.operations.live_scope import redactor_for
from tests.events.manual_grant_fixture import create_manual_grant
from tests.events.ticketing_helpers import open_event
from tests.fixed_roles.helpers import staff_account
from tests.handout_roles import make_handout_member
from tests.machines.certification_helpers import _member
from tests.return_helpers import authenticated_client, make_space, make_user

pytestmark = pytest.mark.django_db

MODULES = ("notifications", "machines", "events", "bookings", "request_workflow", "staff_admin", "reports")
STAFF_SLUGS = ("space_manager", "inventory_manager", "event_manager", "booking_manager", "shop_manager",
               "technician")
FEED_EVENTS = ("request.submitted", "machine_service.completed", "email.failed", "stocktake.completed", "")


def _space(slug):
    space = make_space(slug)
    Makerspace.objects.filter(pk=space.pk).update(
        enabled_modules=sorted(set(space.enabled_modules or []) | set(MODULES)))
    space.refresh_from_db()
    return space


@pytest.fixture
def world():
    space, other = _space("area0120"), _space("area0120-other")
    laser = MachineType.objects.create(makerspace=space, slug="area0120-laser", name="Laser")
    people = {slug: staff_account(space, f"area0120-{slug}", slug) for slug in STAFF_SLUGS}
    people["machine_manager_laser"] = staff_account(space, "area0120-mm", "machine_manager", machine_types=[laser])
    people["handover"] = make_handout_member("area0120-handover", space)
    people["member"], _ = _member(space, "area0120-member")
    people["borrower"] = make_user("area0120-borrower", access_status=User.AccessStatus.ACTIVE)
    people["foreign_manager"] = staff_account(other, "area0120-foreign", "space_manager")
    feed = {event: Notification.objects.create(makerspace=space, event=event, title=event or "legacy")
            for event in FEED_EVENTS}
    event_a, event_b = open_event(space), open_event(space)
    Event.objects.filter(pk=event_a.pk).update(title="Area A")
    Event.objects.filter(pk=event_b.pk).update(title="Area B")
    InventoryProduct.objects.create(makerspace=space, name="Areascope drill", total_quantity=2,
                                    available_quantity=2)
    return SimpleNamespace(space=space, other=other, laser=laser, people=people, feed=feed,
                           event_a=event_a, event_b=event_b)


def _client(world, who):
    return APIClient() if who == "anonymous" else authenticated_client(world.people[who])


# Dashboard: served to the area managers, a queue view to Handover, refused elsewhere --------

@pytest.mark.parametrize("who,expected", [
    ("space_manager", 200), ("inventory_manager", 200), ("event_manager", 200), ("booking_manager", 200),
    ("machine_manager_laser", 200), ("handover", 200), ("technician", 403), ("shop_manager", 403),
    ("foreign_manager", 404), ("anonymous", 401),
])
def test_dashboard_admission_per_role(world, who, expected):
    response = _client(world, who).get(reverse("operations-dashboard", args=[world.space.pk]))
    assert response.status_code in ((401, 403) if expected == 401 else (expected,)), response.content
    if who == "handover":
        assert response.data["scope_mode"] == "handover" and response.data["widgets"] == []
    if who == "event_manager":
        # No inventory authority: the lending counters stay zero and no loan widget is offered.
        assert response.data.get("pending_requests", 0) == 0
        assert not {w["key"] for w in response.data["widgets"]} & {"most-lent", "top-borrowers", "overdue-loans"}


# Legacy staff feed: each reader sees only the alerts of their own areas ----------------------

@pytest.mark.parametrize("who,visible", [
    ("space_manager", set(FEED_EVENTS)),
    ("inventory_manager", {"request.submitted", "stocktake.completed", ""}),
])
def test_legacy_feed_rows_follow_the_readers_areas(world, who, visible):
    client = _client(world, who)
    response = client.get(reverse("notifications:notifications-list", args=[world.space.pk]))
    assert response.status_code == 200, response.content
    assert {row["event"] for row in response.data["results"]} == visible
    count = client.get(reverse("notifications:notifications-unread-count", args=[world.space.pk]))
    assert count.data["count"] == len(visible)


@pytest.mark.parametrize("who", ["event_manager", "booking_manager", "shop_manager", "technician",
                                 "machine_manager_laser", "handover", "member", "foreign_manager"])
def test_legacy_feed_is_refused_outside_inventory_machines_and_settings(world, who):
    response = _client(world, who).get(reverse("notifications:notifications-list", args=[world.space.pk]))
    assert response.status_code in (403, 404)


def test_inventory_manager_cannot_read_or_mark_another_areas_alert(world):
    client = _client(world, "inventory_manager")
    hidden = world.feed["machine_service.completed"]
    url = reverse("notifications:notifications-read", args=[world.space.pk, hidden.pk])
    assert client.post(url).status_code == 404
    assert client.post(reverse("notifications:notifications-read-all", args=[world.space.pk])).status_code == 200
    hidden.refresh_from_db()
    world.feed["email.failed"].refresh_from_db()
    assert hidden.read_at is None and world.feed["email.failed"].read_at is None
    world.feed["request.submitted"].refresh_from_db()
    assert world.feed["request.submitted"].read_at is not None


# Global search: every entity list re-checks its own action -----------------------------------

ALL_ENTITIES = {"requests", "inventory", "members", "bookings", "events", "machines"}


@pytest.mark.parametrize("who,expected,forbidden", [
    ("space_manager", {"inventory", "events"}, set()),
    ("inventory_manager", {"inventory"}, {"events", "members", "bookings"}),
    ("event_manager", {"events"}, {"inventory", "members", "bookings", "requests"}),
    ("booking_manager", set(), {"inventory", "members", "events", "requests"}),
    ("shop_manager", set(), ALL_ENTITIES),
    ("technician", set(), ALL_ENTITIES),
])
def test_staff_search_returns_only_the_readers_entities(world, who, expected, forbidden):
    response = _client(world, who).get(reverse("admin-search"), {"makerspace_id": world.space.pk, "q": "Area"})
    if response.status_code in (403, 404):
        assert not expected
        return
    assert response.status_code == 200, response.content
    entities = {hit["entity"] for hit in response.data["results"]}
    assert expected <= entities and not entities & forbidden, entities


def test_search_refuses_another_space(world):
    response = _client(world, "foreign_manager").get(
        reverse("admin-search"), {"makerspace_id": world.space.pk, "q": "Areascope"})
    assert response.status_code == 404


# Event related facts: a co-organizer limited to one event reads that event only --------------

def test_event_coorganizer_reads_only_their_own_event(world):
    helper = world.people["inventory_manager"]
    create_manual_grant(makerspace=world.space, event=world.event_a, user=helper,
                        permissions=["manage_registrations"])
    client = authenticated_client(helper)
    own = client.get(reverse("admin-related-facts-event", args=[world.space.pk, world.event_a.pk]))
    assert own.status_code == 200, own.content
    assert own.data["subject"]["id"] == world.event_a.pk and "registrations" in own.data
    other = client.get(reverse("admin-related-facts-event", args=[world.space.pk, world.event_b.pk]))
    assert other.status_code in (403, 404)
    foreign = authenticated_client(world.people["foreign_manager"]).get(
        reverse("admin-related-facts-event", args=[world.space.pk, world.event_a.pk]))
    assert foreign.status_code in (403, 404)
    assert Event.objects.filter(pk=world.event_b.pk).exists()


# Live hints: who acted and on what travel only inside the reader's areas ---------------------

def _hint(kind, actor_id, target_id="42"):
    return json.dumps({"kind": kind, "makerspace_id": 1, "target_type": "x", "target_id": target_id,
                       "actor_id": actor_id, "ts": "t"}, separators=(",", ":"))


@pytest.mark.parametrize("who,kind,redacted", [
    ("member", "payment.refunded", True),
    ("member", "request.accepted", True),
    ("shop_manager", "member.revoked", True),
    ("shop_manager", "shop.order_paid", False),
    ("inventory_manager", "request.accepted", False),
    ("inventory_manager", "payment.refunded", True),
    ("booking_manager", "booking.created", False),
    ("booking_manager", "event.published", True),
    ("space_manager", "payment.refunded", False),
])
def test_live_hints_redact_actor_and_target_outside_the_area(world, who, kind, redacted):
    reader = world.people[who]
    channel = live.makerspace_channel(world.space.pk)
    someone_else = world.people["foreign_manager"].pk
    out = json.loads(redactor_for(reader)(channel, _hint(kind, someone_else)))
    assert out["kind"] == kind  # the console still invalidates by kind
    assert (out["actor_id"] is None and out["target_id"] == "") is redacted
    own = json.loads(redactor_for(reader)(channel, _hint(kind, reader.pk)))
    assert own["actor_id"] == reader.pk  # the actor always sees their own hint
    personal = redactor_for(reader)(live.user_channel(reader.pk), _hint(kind, someone_else))
    assert json.loads(personal)["actor_id"] == someone_else


def test_superadmin_stream_is_unredacted():
    root = make_user("area0120-root", role=User.Role.SUPERADMIN, is_superuser=True)
    assert redactor_for(root) is None
