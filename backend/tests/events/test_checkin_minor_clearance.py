"""EV-27: event check-in re-checks guardian consent with the helper registration uses.

Consent that expires or is withdrawn after registration must stop attendance on the online path and be
reported as a typed outcome (not a crash) by the offline sync. Written, not run.
"""
from unittest import mock

import pytest

from apps.events.models import EventRegistration
from apps.events.services_checkin import mark_attended
from apps.events.services_checkin_sync import _process
from apps.makerspaces.community_policy import CommunityError
from tests.events.checkin_helpers import make_event, make_member, make_space, register

pytestmark = pytest.mark.django_db
HELPER = "apps.makerspaces.minors_guard.require_minor_clearance"


def _refuse(*_a, **_k):
    raise CommunityError("guardian_consent_expired", "Consent expired.", 403)


def test_online_check_in_refused_when_guardian_consent_lapsed():
    space = make_space("minor-checkin")
    registration = register(make_event(space), make_member(space))
    with mock.patch(HELPER, side_effect=_refuse) as guard:
        with pytest.raises(CommunityError) as caught:
            mark_attended(registration, actor=None)
    assert caught.value.error_code == "guardian_consent_expired"
    guard.assert_called_once()
    assert guard.call_args.args[2] == "event"
    registration.refresh_from_db()
    assert registration.status == EventRegistration.Status.REGISTERED


def test_check_in_passes_when_guardian_clearance_holds():
    space = make_space("minor-ok")
    registration = register(make_event(space), make_member(space))
    # An online check-in is a staffer's act (the DB constraint requires an actor for it).
    from tests.events.collab_helpers import make_staff
    with mock.patch(HELPER, return_value=None):
        updated = mark_attended(registration, actor=make_staff(space))
    assert updated.status == EventRegistration.Status.ATTENDED


def test_offline_sync_reports_the_typed_code():
    space = make_space("minor-sync")
    event = make_event(space)
    registration = register(event, make_member(space))
    item = {"operation_id": "00000000-0000-4000-8000-000000000027",
            "checkin_token": str(registration.checkin_token), "reported_occurred_at": None}
    with mock.patch("apps.events.services_checkin_sync.reported_time_is_valid", return_value=True), \
            mock.patch("apps.events.services_checkin_sync.mark_attended_with_event", side_effect=_refuse):
        result = _process(event, item, lease={}, actor=None, source="offline_sync", session_id=None,
                          station_version=None)
    assert result["outcome"] == "guardian_consent_expired"
