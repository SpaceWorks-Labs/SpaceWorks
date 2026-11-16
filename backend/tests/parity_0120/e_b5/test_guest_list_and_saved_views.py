"""C16/D22/B25: reply and collected filters, per-list CSV columns, counted presets, per-event saved views."""
from uuid import uuid4

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.events import checkin_lists
from apps.events.models import EventAttendanceReply
from apps.operations.models_saved_views import SavedView
from tests.events.collab_helpers import client_for, make_event, make_member
from tests.events.test_registration_cancel_api import register
from tests.parity_0120.e_b5.helpers import world

pytestmark = pytest.mark.django_db
FEATURES = ("events.saved_views", "events.event_saved_views", "events.checkin_lists",
            "events.attendance_confirmation")


def guests_url(event, tail=""):
    return reverse("events-programme-admin-staff-list" + tail, kwargs={"pk": event.pk, "list_key": "guests"})


def views_url(space, pk=None):
    if pk is None:
        return reverse("admin-saved-views", kwargs={"makerspace_id": space.pk})
    return reverse("admin-saved-view-detail", kwargs={"makerspace_id": space.pk, "pk": pk})


def build(slug):
    space, event, staff = world(slug, *FEATURES)
    yes, quiet = make_member(space, f"{slug}-y"), make_member(space, f"{slug}-q")
    first, second = register(event, yes), register(event, quiet)
    EventAttendanceReply.objects.create(makerspace=space, event=event, registration=first, asked_at=timezone.now(),
                                        answer="yes", replied_at=timezone.now())
    return space, event, staff, first, second


def test_reply_and_collected_filters_and_csv_columns():
    _space, event, staff, first, second = build("gl-a")
    swag = checkin_lists.create(event, actor=staff, data={"name": "Swag"})
    checkin_lists.scan(event, actor=staff, list_id=swag.pk, registration_id=first.pk, operation_id=uuid4())
    client = client_for(staff)
    replied = client.get(guests_url(event), {"reply": "yes"}).data
    assert [row["id"] for row in replied["results"]] == [first.pk]
    assert "Check-in: Swag" in replied["columns"]
    missing = client.get(guests_url(event), {"list": swag.pk, "collected": "no"}).data
    assert [row["id"] for row in missing["results"]] == [second.pk]
    export = client.get(guests_url(event, "-export"), {"list": swag.pk, "collected": "yes"})
    body = b"".join(export.streaming_content).decode()
    assert body.splitlines()[0].endswith("Check-in: Swag") and str(first.pk) in body


def test_presets_carry_server_counts():
    _space, event, staff, _first, _second = build("gl-b")
    data = client_for(staff).get(guests_url(event, "-presets")).data["results"]
    counts = {row["key"]: row["count"] for row in data}
    assert counts["all"] == 2 and counts["confirmed"] == 2 and counts["waiting_reply"] == 0


def test_a_view_saved_on_one_event_never_shows_on_another_and_can_be_renamed():
    space, event, staff, _first, _second = build("gl-c")
    other_event = make_event(space, is_public=True)
    client = client_for(staff)
    created = client.post(views_url(space), {"name": "Waiting", "entity": "event_guests",
                                             "state": {"event": str(event.pk), "reply": "waiting"}}, format="json")
    assert created.status_code == 201
    scoped = client.get(views_url(space), {"entity": "event_guests", "event": event.pk})
    elsewhere = client.get(views_url(space), {"entity": "event_guests", "event": other_event.pk})
    spacewide = client.get(views_url(space), {"entity": "event_guests"})
    assert scoped.data["count"] == 1 and elsewhere.data["count"] == 0 and spacewide.data["count"] == 0
    renamed = client.patch(views_url(space, created.data["id"]), {"name": "Still waiting"}, format="json")
    assert renamed.status_code == 200 and SavedView.objects.get(pk=created.data["id"]).name == "Still waiting"


def test_saved_view_limit_is_per_person_per_event_list():
    space, event, staff, _first, _second = build("gl-d")
    space.resource_limit_overrides = {"saved_views": 1}
    space.save(update_fields=["resource_limit_overrides"])
    client = client_for(staff)
    body = {"entity": "event_guests", "state": {"event": str(event.pk)}}
    assert client.post(views_url(space), {"name": "A", **body}, format="json").status_code == 201
    assert client.post(views_url(space), {"name": "B", **body}, format="json").status_code == 409


def test_event_scoped_view_needs_the_switch():
    space, event, staff, _first, _second = build("gl-e")
    space.enabled_features = [key for key in space.enabled_features if key != "events.event_saved_views"]
    space.save(update_fields=["enabled_features"])
    created = client_for(staff).post(views_url(space), {"name": "X", "entity": "event_guests",
                                                        "state": {"event": str(event.pk)}}, format="json")
    assert created.status_code in (403, 404)
