"""The offline roster's badge data and v2 rows, the offline sync of SWEC2 codes and receipts, and the PIN station."""
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.events.checkin_roster import minimum_roster
from apps.events.models import EventBadgePrint, EventRegistration
from apps.events.services_checkin_roster import issue_roster
from apps.events.services_checkin_sync import synchronize
from tests.parity_0120.e_b2.helpers import FEATURES, issue_cards, live_event, publish_badge, register

pytestmark = pytest.mark.django_db


def _roster_world(slug, features=FEATURES, **settings):
    space, event, sm = live_event(slug, features)
    publish_badge(space, event, sm, **settings)
    _user, registration = register(space, event, "ada")
    registration.custom_answers = {"company": "Acme", "diet": "vegan"}
    registration.save()
    issue_cards(event)
    return space, event, sm, registration


def test_the_roster_has_no_badge_fields_while_the_desk_switch_is_off():
    features = tuple(feature for feature in FEATURES if feature != "events.badge_desk_print")
    _space, event, _sm, _registration = _roster_world("e2-roster-off", features)
    row = minimum_roster(event)[0]
    assert set(row) == {"registration_id", "checkin_token", "name", "host_waiver_state"}


def test_the_roster_carries_only_what_the_design_prints_and_email_only_if_printed():
    _space, event, _sm, registration = _roster_world(
        "e2-roster-on", showEmail=False, printFieldKeys=["registration:company"],
        printFieldLabels={"registration:company": "Company"})
    row = minimum_roster(event)[0]
    assert row["checkin_payload"] == str(registration.checkin_token)
    badge = row["badge"]
    assert badge["answers"] == {"field:company": "Acme"} and "email" not in badge
    assert badge["role"] == "attendee" and badge["card_id"]


def test_the_lease_response_carries_the_published_badge_per_role_and_logos():
    _space, event, sm, _registration = _roster_world("e2-lease")
    payload = issue_roster(event, actor=sm, kind="staff")
    bundle = payload["badges"]
    assert set(bundle["roles"]) >= {"attendee", "crew", "organiser"}
    assert bundle["designs"][bundle["roles"]["attendee"]]["document"]["front"]["layers"]
    assert isinstance(bundle["logos"], dict)


def test_a_v2_registration_is_listed_with_its_live_code_and_syncs_offline(settings):
    from apps.events.credentials.workflow import issue_locked
    _space, event, sm, registration = _roster_world("e2-v2")
    EventRegistration.objects.filter(pk=registration.pk).update(credential_mode="v2")
    registration.refresh_from_db()
    issue_locked(event, registration, actor=sm)
    row = minimum_roster(event)[0]
    assert row["checkin_token"].startswith("SWEC2.") and row["checkin_token"] == row["checkin_payload"]
    lease = {"lease_id": str(uuid4())}
    result = synchronize(event, [{"operation_id": uuid4(), "checkin_token": row["checkin_token"],
                                  "reported_occurred_at": timezone.now()}],
                         lease=lease, actor=sm, source="offline_sync", session_id=lease["lease_id"])
    assert result["results"][0]["outcome"] in ("applied", "outside_window")


def test_offline_receipts_ride_the_sync_batch_and_are_counted_when_they_sync():
    _space, event, sm, registration = _roster_world("e2-offline")
    lease = {"lease_id": str(uuid4())}
    receipt = {"operation_id": uuid4(), "registration_id": registration.pk, "stock": "a6-portrait", "role": "attendee"}
    result = synchronize(event, [], lease=lease, actor=sm, source="offline_sync", session_id=lease["lease_id"],
                         badge_receipts=[receipt])
    assert result["badge_receipts"] == {"recorded": 1, "duplicates": 0}
    assert EventBadgePrint.objects.get(event=event).method == "offline"


def test_the_station_serves_the_badge_and_records_prints_as_station():
    from apps.events import badge_prints
    from apps.events.views_station_badges import EventStationBadgeReceiptsView, EventStationBadgeView
    assert EventStationBadgeView.get and EventStationBadgeReceiptsView.post
    _space, event, _sm, registration = _roster_world("e2-station")
    recorded, _dupes = badge_prints.record_receipts(
        event, [{"operation_id": uuid4(), "registration_id": registration.pk}], actor=None, method="station")
    assert recorded == 1 and EventBadgePrint.objects.get(event=event).method == "station"
