"""Retaining designs during recurrence edits must not publish draft history."""

from datetime import time, timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.events.models import Event, EventCertificateArtwork
from apps.events.services_certificate_templates import save_template
from apps.events.services_series import create_series, publish_series, update_series
from tests.events.collab_helpers import make_staff
from tests.events.test_event_calendars import public_url
from tests.events.ticketing_helpers import event_space


@pytest.mark.django_db
@pytest.mark.parametrize("published", [False, True])
@pytest.mark.parametrize("design_kind", ["revision", "artwork"])
def test_retained_occurrence_calendar_respects_prior_publication(published, design_kind):
    space = event_space("retained-calendar")
    space.enabled_features += ["events.certificate_designer"]
    space.save(update_fields=["enabled_features"])
    actor = make_staff(space)
    series, events = create_series(
        makerspace=space, actor=actor, title="Unpublished workshop details",
        recurrence_timezone="UTC", dtstart_local_date=(timezone.now() + timedelta(days=1)).date(),
        dtstart_local_time=time(10), recurrence_rule="FREQ=DAILY;COUNT=2",
        duration_minutes=60, is_public=True,
    )
    if published:
        series, _count = publish_series(series, actor=actor)
    event = events[0]
    if design_kind == "revision":
        design = save_template(event, actor=actor, parameters={})
    else:
        # An upload reservation alone also protects an occurrence from deletion.
        design = EventCertificateArtwork.objects.create(
            event=event, object_key=f"events/certificate-artwork/{space.pk}/reserved.png",
        )
    client = APIClient()
    url = public_url(space, event)
    assert client.get(url).status_code == (200 if published else 404)

    series, created, removed = update_series(
        series, actor=actor, effective_from=timezone.now(), dtstart_local_time=time(12),
    )

    event.refresh_from_db()
    design.refresh_from_db()
    assert event.status == Event.Status.CANCELLED
    assert design.event_id == event.pk
    assert event.pk not in removed and created
    assert event.is_public is published
    assert client.get(url).status_code == (200 if published else 404)
    if not published:
        publish_series(series, actor=actor)
        assert client.get(url).status_code == 404
        assert client.get(public_url(space, created[0])).status_code == 200
