"""Final audit 0.12.0 M5: cancelling or moving an event takes its guest passes with it."""
from datetime import timedelta

import pytest

from apps.events import guest_pass_event_changes
from apps.makerspaces.models import GuestPass
from tests.events.checkin_helpers import make_event, register
from tests.events.test_guest_pass_adapter_223 import _events_space
from tests.makerspaces.test_membership_j1 import user

pytestmark = pytest.mark.django_db(transaction=True)


def _pass(slug):
    makerspace = _events_space(slug)
    event = make_event(makerspace)
    guest = user(f"{slug}-guest")
    register(event, guest)
    return event, GuestPass.objects.get(makerspace=makerspace, holder=guest, kind="event")


def test_cancelled_event_revokes_its_live_passes():
    event, row = _pass("ec-cancel")
    assert guest_pass_event_changes.revoke_passes_for_cancelled_event(event.pk) == 1
    row.refresh_from_db()
    assert row.status == GuestPass.Status.REVOKED


def test_moved_event_rewindows_its_live_passes_to_the_new_dates():
    event, row = _pass("ec-move")
    event.starts_at += timedelta(days=3)
    event.ends_at += timedelta(days=3)
    event.save(update_fields=["starts_at", "ends_at"])
    assert guest_pass_event_changes.rewindow_passes_for_moved_event(event.pk) == 1
    moved = GuestPass.objects.get(pk=row.pk)
    assert moved.status == row.status and moved.valid_from == event.starts_at - timedelta(hours=1)
    assert moved.valid_from > row.valid_from
