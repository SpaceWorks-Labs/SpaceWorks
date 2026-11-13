from datetime import time, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.events import services_series
from apps.events.event_permissions import PERMISSIONS
from apps.accounts.serializers_payload import user_payload
from tests.events.collab_helpers import client_for
from tests.events.staff_grant_helpers import grant_fixture
from tests.events.test_image import mock_public_storage

pytestmark = pytest.mark.django_db

OPERATIONS = [
    ("edit_details", "patch", "admin-event-series-detail", {"title": "Edited series"}),
    ("publish_schedule", "patch", "admin-event-series-detail", {"duration_minutes": 90}),
    ("publish_schedule", "post", "admin-event-series-publish", {}),
    ("publish_schedule", "post", "admin-event-series-extend", {}),
    ("publish_schedule", "post", "admin-event-series-cancel", {}),
    ("publish_schedule", "post", "admin-event-series-complete", {}),
    ("edit_details", "post", "admin-event-series-image", {"content_type": "image/png", "filename": "poster.png"}),
    ("edit_details", "put", "admin-event-series-image", {}),
    ("edit_details", "delete", "admin-event-series-image", {}),
]


def series_fixture(held, *, past=False):
    space, manager, user, _, grant = grant_fixture(held)
    series, _ = services_series.create_series(
        makerspace=space, actor=manager, title="Granted series", registration_audience="accounts",
        recurrence_timezone="UTC", dtstart_local_date=(timezone.now() + timedelta(days=-1 if past else 1)).date(),
        dtstart_local_time=time(12), recurrence_rule="FREQ=DAILY;COUNT=1", duration_minutes=60,
    )
    grant.event = None
    grant.series = series
    grant.save(update_fields=["event", "series"])
    # Authority follows the live manual source, so re-issue it for the series target.
    from tests.events.staff_grant_helpers import set_grant_permissions
    set_grant_permissions(grant, list(grant.permissions))
    return manager, user, series


@pytest.mark.parametrize("held", PERMISSIONS)
@pytest.mark.parametrize("required,method,route,payload", OPERATIONS)
def test_series_operations_use_schedule_and_details_permissions_separately(held, required, method, route, payload, monkeypatch):
    manager, user, series = series_fixture(held, past=route.endswith("complete"))
    data = dict(payload)
    if route.endswith(("cancel", "complete")):
        services_series.publish_series(series, actor=manager)
    if route == "admin-event-series-image":
        mock_public_storage(monkeypatch)
        if method in ("put", "delete"):
            uploaded = client_for(manager).post(reverse(route, args=[series.pk]), {
                "content_type": "image/png", "filename": "poster.png",
            }, format="json")
            assert uploaded.status_code == 201
            if method == "put":
                data = {"object_key": uploaded.data["object_key"]}
            else:
                series.image_key = uploaded.data["object_key"]
                series.save(update_fields=["image_key"])
    response = getattr(client_for(user), method)(reverse(route, args=[series.pk]), data, format="json")
    if held == required:
        assert response.status_code < 300, (route, response.data)
    else:
        assert response.status_code == 403, (route, response.data)


@pytest.mark.parametrize("held", ["edit_details", "publish_schedule"])
def test_mixed_recurrence_and_details_update_requires_both_permissions(held):
    _, user, series = series_fixture(held)
    response = client_for(user).patch(reverse("admin-event-series-detail", args=[series.pk]), {
        "title": "Mixed edit", "duration_minutes": 90,
    }, format="json")
    assert response.status_code == 403
    series.refresh_from_db()
    assert series.title == "Granted series" and series.duration_minutes == 60


def test_empty_granted_series_is_discovered_before_it_has_occurrences():
    _, user, series = series_fixture("publish_schedule", past=True)
    assert not series.occurrences.exists()
    entries = user_payload(user)["event_grants"]
    assert entries == [{
        "event_id": None, "series_id": series.pk,
        "makerspace_id": series.makerspace_id, "makerspace_slug": series.makerspace.slug,
        "title": series.title, "source": "event_grant", "permissions": ["publish_schedule"],
    }]
    response = client_for(user).get(reverse("admin-event-series-detail", args=[series.pk]))
    assert response.status_code == 200


@pytest.mark.parametrize("held", ["check_in", "manage_registrations", "manage_invitations"])
@pytest.mark.parametrize("effective_only", [False, True])
def test_non_editor_cannot_materialize_series_through_empty_or_effective_only_patch(held, effective_only):
    _, user, series = series_fixture(held)
    before = set(series.occurrences.values_list("pk", flat=True))
    payload = {"effective_from": timezone.now().isoformat()} if effective_only else {}
    response = client_for(user).patch(reverse("admin-event-series-detail", args=[series.pk]), payload, format="json")
    assert response.status_code == 403
    assert set(series.occurrences.values_list("pk", flat=True)) == before
