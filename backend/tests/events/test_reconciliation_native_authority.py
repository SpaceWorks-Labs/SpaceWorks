"""Native device context survives reload and cannot borrow organizer delegation."""
from datetime import time

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.native_session import _NATIVE_USER_ID
from apps.events.models import Event, EventOrganizer, EventSeries, EventSeriesOrganizer
from apps.events.organizer_authority import can_manage_event, organizer_event_q
from apps.events.series_authority import can_manage_series, organizer_series_q
from apps.organizations.models import Organization, OrganizationMembership
from tests.events.test_services import make_event
from tests.return_helpers import make_space, make_user

pytestmark = pytest.mark.django_db


def test_member_native_context_refuses_event_and_series_organization_authority():
    space = make_space("recon-native-organizer")
    actor = make_user("recon-native-organizer", access_status="active")
    organization = Organization.objects.create(name="Organizers", slug="recon-native-organizer")
    OrganizationMembership.objects.create(organization=organization, user=actor, granted_actions=["manage_events"])
    event = make_event(space)
    series = EventSeries.objects.create(makerspace=space, title="Series", recurrence_timezone="UTC",
        dtstart_local_date=timezone.now().date(), dtstart_local_time=time(12),
        recurrence_rule="FREQ=DAILY", duration_minutes=60)
    EventOrganizer.objects.create(event=event, organization=organization)
    EventSeriesOrganizer.objects.create(series=series, organization=organization)
    assert can_manage_event(actor, event) and can_manage_series(actor, series)
    assert Event.objects.filter(organizer_event_q(actor), pk=event.pk).exists()
    assert EventSeries.objects.filter(organizer_series_q(actor), pk=series.pk).exists()
    token = _NATIVE_USER_ID.set(actor.pk)
    try:
        reloaded = User.objects.get(pk=actor.pk)
        assert not can_manage_event(reloaded, event)
        assert not can_manage_series(reloaded, series)
        assert not Event.objects.filter(organizer_event_q(reloaded)).exists()
        assert not EventSeries.objects.filter(organizer_series_q(reloaded)).exists()
    finally:
        _NATIVE_USER_ID.reset(token)
