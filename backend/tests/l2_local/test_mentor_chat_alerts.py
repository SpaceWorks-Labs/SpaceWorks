"""G9 Mentor Desk help alerts: chosen rooms only, on-shift only, outbound text, quiet hours, switch."""
from types import SimpleNamespace

import pytest
from rest_framework.exceptions import ValidationError

from apps.events.mentoring import chat_alerts
from apps.events.models_r2_l2 import MentorAlertRoute
from apps.integrations.models_destinations import NotificationDestination
from tests.events.collab_helpers import make_staff
from tests.events.ticketing_helpers import event_space, open_event
from tests.l2_local.helpers import off, on

pytestmark = pytest.mark.django_db
PAYLOAD = {"event_id": 1, "team_alias": "Team Kestrel", "category": "hardware", "priority": "high"}


def setup(monkeypatch, *, quiet=False):
    space = event_space("mentor-alerts")
    staff = make_staff(space)
    event = open_event(space)
    room = NotificationDestination.objects.create(makerspace=space, channel="telegram", label="Mentors",
                                                  telegram_chat_id="-100")
    other = event_space("someone-else")
    foreign = NotificationDestination.objects.create(makerspace=other, channel="telegram", label="X",
                                                     telegram_chat_id="-200")
    sent, audits = [], []
    monkeypatch.setattr("apps.integrations.dispatch_destination.deliver_text_to_destination",
                        lambda space, destination, **kw: sent.append((destination.pk, kw["text"])) or (True, ""))
    monkeypatch.setattr("apps.integrations.quiet_hours.quiet_until", lambda *args: object() if quiet else None)
    monkeypatch.setattr(chat_alerts, "record", lambda *args, **kwargs: audits.append(kwargs["meta"]))
    monkeypatch.setattr(chat_alerts, "_already_posted", lambda intent, destination: False)
    return space, staff, event, room, foreign, sent, audits


def intent(space, kind="created"):
    return SimpleNamespace(pk=7, kind=kind, makerspace_id=space.pk)


def test_off_posts_nothing_and_on_posts_to_the_chosen_room_without_names(monkeypatch):
    space, staff, event, room, _foreign, sent, audits = setup(monkeypatch)
    MentorAlertRoute.objects.create(event=event, makerspace=space, destination=room, created_by=staff)
    off(space, "events.mentor_chat_alerts")
    assert chat_alerts.post_help_alert(intent(space), event, PAYLOAD, (1,)) == 0
    on(space, "events.hackathons", "events.mentoring", "events.mentor_chat_alerts")
    assert chat_alerts.post_help_alert(intent(space), event, PAYLOAD, (1, 2)) == 1
    assert sent[0][0] == room.pk and "2 mentors are on shift" in sent[0][1]
    assert audits[0]["channel"] == "telegram" and "text" not in audits[0]


def test_no_mentor_on_shift_or_a_non_new_notice_posts_nothing(monkeypatch):
    space, staff, event, room, _foreign, sent, _audits = setup(monkeypatch)
    on(space, "events.hackathons", "events.mentoring", "events.mentor_chat_alerts")
    MentorAlertRoute.objects.create(event=event, makerspace=space, destination=room, created_by=staff)
    assert chat_alerts.post_help_alert(intent(space), event, PAYLOAD, ()) == 0
    assert chat_alerts.post_help_alert(intent(space, "attention"), event, PAYLOAD, (1,)) == 0
    assert sent == []


def test_quiet_hours_hold_room_posts(monkeypatch):
    space, staff, event, room, _foreign, sent, audits = setup(monkeypatch, quiet=True)
    on(space, "events.hackathons", "events.mentoring", "events.mentor_chat_alerts")
    MentorAlertRoute.objects.create(event=event, makerspace=space, destination=room, created_by=staff)
    assert chat_alerts.post_help_alert(intent(space), event, PAYLOAD, (1,)) == 0
    assert sent == [] and audits[0]["error"] == "quiet_hours"


def test_routes_accept_only_this_spaces_rooms(monkeypatch):
    space, staff, event, room, foreign, _sent, _audits = setup(monkeypatch)
    monkeypatch.setattr(chat_alerts, "record", lambda *args, **kwargs: None)
    with pytest.raises(ValidationError):
        chat_alerts.set_routes(event, staff, [foreign.pk])
    assert chat_alerts.set_routes(event, staff, [room.pk]) == [room.pk]
    assert list(chat_alerts.routes(event).values_list("destination_id", flat=True)) == [room.pk]
