"""Open items A19/A20: staff event payloads carry the venue's slug for cross-space drawers."""
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.events.models import Event
from tests.events.collab_helpers import client_for
from tests.events.orders_helpers import l6_space, make_staff

pytestmark = pytest.mark.django_db


def test_event_detail_includes_the_venue_slug():
    space = l6_space("slug-a20")
    manager = make_staff(space, "slug-mgr")
    starts = timezone.now() + timedelta(days=1)
    event = Event.objects.create(makerspace=space, title="Slugged", starts_at=starts, ends_at=starts + timedelta(hours=1),
                                 registration_audience="accounts", is_public=True, status="draft")
    response = client_for(manager).get(reverse("admin-event-detail", kwargs={"pk": event.pk}))
    assert response.status_code == 200
    assert response.json()["makerspace_slug"] == space.slug
