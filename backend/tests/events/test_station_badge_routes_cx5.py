"""Real station-cookie badge reads and receipts, including origin, scope and switches."""
from uuid import uuid4

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.events.models import EventBadgePrint
from apps.events.services_station import STATION_COOKIE_NAME
from tests.events.test_event_checkin_station import (
    STATION_HEADERS, rotate_station, start_station, station_settings,
)
from tests.l3_local.helpers import client
from tests.parity_0120.e_b2.helpers import issue_cards, live_event, publish_badge, register
from tests.refusal_helpers_mod2b import refused

pytestmark = pytest.mark.django_db


@pytest.fixture
def desk(station_settings):
    space, event, manager = live_event("cx5-station")
    publish_badge(space, event, manager)
    member, registration = register(space, event, "attendee")
    issue_cards(event)
    credentials = rotate_station(event, manager)
    api, response = start_station(credentials)
    assert response.status_code == 204, response.content
    assert response.cookies[STATION_COOKIE_NAME].value
    assert api.cookies[STATION_COOKIE_NAME].value == response.cookies[STATION_COOKIE_NAME].value
    assert response["Cache-Control"] == "private, no-store"
    return space, event, manager, member, registration, credentials, api


def url(desk, operation):
    _space, _event, _manager, _member, registration, credentials, _api = desk
    values = {"public_token": credentials["public_token"]}
    if operation == "badge":
        values["registration_id"] = registration.pk
    return reverse("event-check-in-station-" + operation, kwargs=values)


def body(desk):
    return {"receipts": [{"operation_id": str(uuid4()), "registration_id": desk[4].pk,
                           "stock": "a6-portrait", "role": "attendee"}]}


def call(api, desk, operation, data=None, headers=None):
    headers = STATION_HEADERS if headers is None else headers
    if operation == "badge":
        return api.get(url(desk, operation), **headers)
    return api.post(url(desk, operation), data or body(desk), format="json", **headers)


def test_station_badge_is_private_and_receipt_replay_audits_once(desk):
    space, event, _manager, _member, registration, _credentials, api = desk
    got = call(api, desk, "badge")
    assert got.status_code == 200, got.content
    assert got["Cache-Control"] == "private, no-store"
    assert got.json()["event"]["id"] == event.pk
    assert got.json()["badge"]["registration_id"] == registration.pk
    data = body(desk)
    first = call(api, desk, "badge-receipts", data)
    assert first.status_code == 200 and first.json() == {"recorded": 1, "duplicates": 0}
    replay = call(api, desk, "badge-receipts", data)
    assert replay.status_code == 200 and replay.json() == {"recorded": 0, "duplicates": 1}
    row = EventBadgePrint.objects.get(event=event)
    assert row.registration_id == registration.pk and row.method == "station" and row.actor_id is None
    assert AuditLog.objects.filter(makerspace=space, action="event_badge.printed").count() == 1


@pytest.mark.parametrize("operation", ["badge", "badge-receipts"])
@pytest.mark.parametrize("role", ["signed_out", "member", "space_manager", "other_station"])
def test_bearer_staff_and_members_cannot_replace_the_bound_station_cookie(desk, operation, role):
    _space, _event, manager, member, _registration, _credentials, _api = desk
    api = APIClient() if role == "signed_out" else client(member if role == "member" else manager)
    if role == "other_station":
        _other_space, other_event, other_manager = live_event("cx5-other-station")
        credentials = rotate_station(other_event, other_manager)
        api, started = start_station(credentials)
        assert started.status_code == 204, started.content
        assert started.cookies[STATION_COOKIE_NAME].value
        assert api.cookies[STATION_COOKIE_NAME].value == started.cookies[STATION_COOKIE_NAME].value
        assert started["Cache-Control"] == "private, no-store"
    refused(call(api, desk, operation), 403, "permission_denied")
    assert not EventBadgePrint.objects.filter(event=desk[1]).exists()


@pytest.mark.parametrize("operation", ["badge", "badge-receipts"])
@pytest.mark.parametrize("headers", [{}, {"HTTP_ORIGIN": "https://hostile.test", "HTTP_X_STATION_CSRF": "present"},
                                      {"HTTP_ORIGIN": STATION_HEADERS["HTTP_ORIGIN"]}])
def test_station_cookie_alone_never_bypasses_origin_and_csrf(desk, operation, headers):
    refused(call(desk[-1], desk, operation, headers=headers), 403, "permission_denied")
    assert not EventBadgePrint.objects.filter(event=desk[1]).exists()


@pytest.mark.parametrize("operation", ["badge", "badge-receipts"])
@pytest.mark.parametrize("key", ["events.id_cards", "events.badge_desk_print"])
def test_badge_switches_restore_the_same_station_and_registration(desk, operation, key):
    space, event, _manager, _member, registration, _credentials, api = desk
    original = list(space.enabled_features)
    space.enabled_features = [item for item in original if item != key]
    space.save(update_fields=["enabled_features"])
    refused(call(api, desk, operation), 404, "feature_disabled")
    assert not EventBadgePrint.objects.filter(event=event).exists()
    space.enabled_features = original
    space.save(update_fields=["enabled_features"])
    restored = call(api, desk, operation)
    assert restored.status_code == 200, restored.content
    if operation == "badge":
        assert restored.json()["badge"]["registration_id"] == registration.pk
    else:
        assert restored.json() == {"recorded": 1, "duplicates": 0}


@pytest.mark.parametrize("operation", ["badge", "badge-receipts"])
@pytest.mark.parametrize("key", ["events", "events.offline_checkin"])
def test_station_module_admission_has_a_uniform_refusal_and_recovers(desk, operation, key):
    space, event, _manager, _member, _registration, _credentials, api = desk
    field = "enabled_modules" if key == "events" else "enabled_features"
    original = list(getattr(space, field))
    setattr(space, field, [item for item in original if item != key])
    space.save(update_fields=[field])
    # Station credentials intentionally conceal disabled, expired and unknown sessions alike.
    refused(call(api, desk, operation), 403, "permission_denied")
    assert not EventBadgePrint.objects.filter(event=event).exists()
    setattr(space, field, original)
    space.save(update_fields=[field])
    assert call(api, desk, operation).status_code == 200


def test_station_does_not_serve_or_record_another_events_registration(desk):
    space, event, _manager, _member, _registration, credentials, api = desk
    other_space, other_event, _sm = live_event("cx5-station-foreign-registration")
    _other_member, foreign = register(other_space, other_event, "foreign")
    foreign_url = reverse("event-check-in-station-badge", kwargs={
        "public_token": credentials["public_token"], "registration_id": foreign.pk})
    refused(api.get(foreign_url, **STATION_HEADERS), 404, "not_found")
    data = body(desk)
    data["receipts"][0]["registration_id"] = foreign.pk
    result = call(api, desk, "badge-receipts", data)
    assert result.status_code == 200 and result.json() == {"recorded": 0, "duplicates": 1}
    assert not EventBadgePrint.objects.filter(event=event).exists()
    assert not AuditLog.objects.filter(makerspace=space, action="event_badge.printed").exists()


@pytest.mark.parametrize("count,code", [(0, "empty"), (201, "invalid")])
def test_station_receipt_batch_boundaries_have_exact_field_codes(desk, count, code):
    data = {"receipts": [{**body(desk)["receipts"][0], "operation_id": str(uuid4())} for _ in range(count)]}
    response = desk[-1].post(url(desk, "badge-receipts"), data, format="json", **STATION_HEADERS)
    assert response.status_code == 400
    errors = response.data["receipts"]
    errors = errors["non_field_errors"] if isinstance(errors, dict) else errors
    assert errors[0].code == code
    assert not EventBadgePrint.objects.filter(event=desk[1]).exists()
