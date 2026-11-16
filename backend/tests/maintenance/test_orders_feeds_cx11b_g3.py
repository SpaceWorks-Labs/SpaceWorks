"""Work-order hidden-stream contract and private calendar feeds (97/128, 220, 481/494)."""
from datetime import timedelta
from hashlib import sha256
from urllib.parse import urlsplit

import pytest
from tests.modules.test_switch_matrix_objects_rest_isolation import cx11b_isolated_phase  # noqa: F401
from django.utils import timezone
from rest_framework.test import APIClient

from apps.maintenance.calendar_feed import issue
from apps.maintenance.models import MaintenanceSchedule, WorkOrder
from apps.maintenance.models_feed import MaintenanceCalendarFeed
from apps.maintenance.repairs import areas
from tests.maintenance.l16_helpers import world
from tests.maintenance.route_support_cx11b_g3 import foreign_client, foreign_refusal, prove, send
from tests.modules.switch_matrix_object_helpers import client_for

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_inventory,
              pytest.mark.area_machines, pytest.mark.area_bookings]
ORDER_CASES = [(op, area, kind, target, field, key, native)
    for op in ("list", "create", "status", "assign") for area, kind, target, field, parent in (
        ("machines", "machine", "machine", "machine", "machines"),
        ("inventory", "inventory_product", "product", "product", "loans.enabled"),
        ("rooms", "bookable_space", "room", "space", "bookings"))
    for key in (areas.MAINTENANCE[area], parent) for native in (False, True)]


@pytest.mark.parametrize("op,area,kind,target,field,key,native", ORDER_CASES)
def test_work_order_effect_standing_and_hidden_stream(op, area, kind, target, field, key, native):
    w = world("g3-orders")
    subject = getattr(w, target)
    row = WorkOrder.objects.create(makerspace=w.space, subject_type=kind, **{field: subject}, title="Retained order")
    client, outsider = client_for(w.manager, w.space, native), foreign_client(native)
    name, args, method, body, status, audit = "admin-work-orders", [w.space.pk], "get", {}, 200, None
    if op == "create":
        method, status, audit = "post", 201, "work_order.created"
        body = {"subject_type": kind, "subject_id": subject.pk, "title": "New order"}
    elif op == "status":
        name, args, method, body, audit = "admin-work-order-status", [row.pk], "post", {"status": "in_progress"}, \
            "work_order.started"
    elif op == "assign":
        name, args, method, body, audit = "admin-work-order-assign", [row.pk], "post", {"assignee_id": w.tech.pk}, \
            "work_order.assigned"

    def check(response):
        if op == "list":
            assert [(r["id"], r["title"], r["subject_id"]) for r in response.data] == [(row.pk, "Retained order", subject.pk)]
        elif op == "create":
            saved = WorkOrder.objects.get(pk=response.data["id"])
            assert (saved.title, saved.subject_type, getattr(saved, field + "_id"), saved.status) == (
                "New order", kind, subject.pk, "open")
            assert WorkOrder.objects.filter(makerspace=w.space).count() == 2
        else:
            row.refresh_from_db()
            if op == "status":
                assert row.status == "in_progress" and row.started_at is not None
            else:
                assert row.assignee_id == w.tech.pk and row.status == "open"

    def hidden(response):
        assert response.data == []

    off = (200, None) if op == "list" else (404, "capability_disabled" if op == "create" else "not_found")
    prove(w.space, {"order": row, "subject": subject}, key,
          lambda c: send(c or client, name, args, method, body), check, status=status, off=off,
          off_check=hidden if op == "list" else None,
          outsiders=[(outsider, foreign_refusal(native, space_path=op in {"list", "create"}))],
          audits={audit: 1} if audit else {})


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["maintenance.calendar_feed", "machines.maintenance", "machines"])
@pytest.mark.parametrize("op", ["get", "post", "delete", "calendar"])
def test_feed_effect_standing_and_switch(op, key, native):
    w = world("g3-feed")
    w.space.enabled_features = sorted(set(w.space.enabled_features) | {"maintenance.calendar_feed"})
    w.space.save(update_fields=["enabled_features"])
    schedule = MaintenanceSchedule.objects.create(machine=w.machine, description="G3 calendar inspection",
        interval_days=14, next_due=timezone.localdate() + timedelta(days=1), created_by=w.manager)
    feed, token = issue(w.manager, w.space)
    before_digest = bytes(feed.token_digest)
    client, outsider = client_for(w.manager, w.space, native), foreign_client(native)

    def call(c):
        if op == "calendar":
            # This is a bearer read with authentication_classes=[]: another
            # account with the valid token has standing. A wrong token has none.
            return send(c or APIClient(), "maintenance-feed-calendar", [w.space.pk, "x" * 43 if c else token])
        return send(c or client, "maintenance-feed", [w.space.pk], op)

    def check(response):
        feed.refresh_from_db()
        if op == "get":
            assert response.data == {"enabled": True, "token_hint": feed.token_hint}
            assert bytes(feed.token_digest) == before_digest
        elif op == "post":
            raw = urlsplit(response.data["feed_url"]).path.rsplit("/", 1)[-1][:-4]
            assert bytes(feed.token_digest) == sha256(raw.encode("ascii")).digest()
            assert bytes(feed.token_digest) != before_digest and feed.revoked_at is None
            assert response.data["token_hint"] == raw[-8:]
            assert MaintenanceCalendarFeed.objects.filter(makerspace=w.space, user=w.manager).count() == 1
        elif op == "delete":
            assert feed.revoked_at is not None and bytes(feed.token_digest) == before_digest
        else:
            from icalendar import Calendar
            events = Calendar.from_ical(response.content).walk("VEVENT")
            assert len(events) == 1 and str(events[0]["DESCRIPTION"]) == "G3 calendar inspection"
            assert w.machine.name in str(events[0]["SUMMARY"])
            assert response["Cache-Control"] == "private, no-store"

    prove(w.space, {"feed": feed, "schedule": schedule}, key, call, check, status=204 if op == "delete" else 200,
          off=(404, "feature_disabled" if key == "maintenance.calendar_feed" else "capability_disabled"),
          outsiders=[(outsider, (404, "not_found") if op == "calendar" else foreign_refusal(native))], audits={"maintenance.feed_rotated": 1} if op == "post" else
          {"maintenance.feed_revoked": 1} if op == "delete" else {})

pytestmark = ([pytestmark] if not isinstance(pytestmark, list) else pytestmark) + [
    pytest.mark.usefixtures("cx11b_isolated_phase")]
