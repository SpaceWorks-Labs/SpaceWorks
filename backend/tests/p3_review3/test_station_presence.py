from datetime import timedelta
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.events.models import Event, EventCheckInEvent, EventRegistration
from apps.events.services_attendance_correction import correct_attendance
from apps.events.services_checkin_sync import synchronize
from apps.events.services_station import binding_for_event
from apps.makerspaces.models import StationCredential
from apps.presence.models import PresenceSession

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("age,corrected,expected", [(0, False, 1), (120, False, 0), (0, True, 0)])
def test_station_sync_bridges_only_fresh_uncorrected_tickets(
    lane, django_capture_on_commit_callbacks, age, corrected, expected,
):
    now = timezone.now()
    lane.space.enabled_features = sorted(set(lane.space.enabled_features) | {"events.offline_checkin"})
    lane.space.save(update_fields=["enabled_features"])
    event = Event.objects.create(makerspace=lane.space, title="Running workshop", status="published",
        starts_at=now - timedelta(hours=1), ends_at=now + timedelta(hours=1), created_by=lane.staff)
    registration = EventRegistration.objects.create(event=event, member=lane.owner, name="Attendee",
                                                    email=lane.owner.email, status="registered")
    binding = binding_for_event(event, create=True, actor=lane.staff)
    credential = StationCredential.objects.create(station=binding.station, pin_digest="unused",
                                                 pin_ciphertext=b"unused")
    lease = {"lease_id": str(uuid4()), "scan_opens_at": event.starts_at,
             "scan_closes_at": event.ends_at, "expires_at": event.ends_at}
    with django_capture_on_commit_callbacks(execute=True):
        result = synchronize(event, [{"operation_id": uuid4(), "checkin_token": registration.checkin_token,
            "reported_occurred_at": now - timedelta(seconds=age)}], lease=lease, actor=None,
            source=EventCheckInEvent.Source.VENUE_STATION, session_id=uuid4(), station_version=credential.version)
        assert result["results"][0]["outcome"] == "applied"
        assert not PresenceSession.objects.filter(event_registration=registration).exists()
        if corrected:
            correct_attendance(registration, actor=lane.staff)
    sessions = PresenceSession.objects.filter(event_registration=registration)
    assert sessions.count() == expected
    if expected:
        assert sessions.get().status == "attending_event"
    registration.refresh_from_db()
    assert registration.status == ("registered" if corrected else "attended")

