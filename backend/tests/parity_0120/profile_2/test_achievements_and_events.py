"""Derived achievements and events attended across spaces (303c, 304c)."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.events.models import Event, EventRegistration
from apps.makerspaces import profile_achievements as ach
from apps.makerspaces.account_profile_activity import attended_events

from .conftest import make_space

pytestmark = pytest.mark.django_db


def attend(user, space, title, **fields):
    start = timezone.now() - timedelta(days=2)
    defaults = dict(makerspace=space, title=title, starts_at=start, ends_at=start + timedelta(hours=2),
                    is_public=True, listing="listed", page_state="live", status=Event.Status.COMPLETED)
    event = Event.objects.create(**{**defaults, **fields})
    return EventRegistration.objects.create(
        event=event, member=user, name=user.display_name, email=user.email, phone="1234567890",
        status=EventRegistration.Status.ATTENDED)


def test_attendance_aggregates_across_member_spaces(ada, space_a, space_b):
    attend(ada, space_a, "A1")
    attend(ada, space_b, "B1")
    assert attended_events(ada)["count"] == 2


def test_private_unlisted_and_draft_events_never_shown(ada, space_a):
    attend(ada, space_a, "Shown")
    attend(ada, space_a, "Private", is_public=False)
    attend(ada, space_a, "Unlisted", listing="unlisted")
    attend(ada, space_a, "Draft", page_state="offline")
    result = attended_events(ada)
    assert result["count"] == 1 and [e["title"] for e in result["recent"]] == ["Shown"]


def test_attendance_only_from_spaces_where_active_member(ada, space_a):
    attend(ada, make_space("outsider"), "Not my space")
    attend(ada, space_a, "Mine")
    assert [e["title"] for e in attended_events(ada)["recent"]] == ["Mine"]


# Published / corrected / withdrawn awards and People's choice winners are covered against real
# judging rows in test_real_results.py.


def test_roles_and_speaking_are_limited_to_member_spaces(ada, monkeypatch):
    seen = {}
    monkeypatch.setattr(ach, "_awards", lambda user: iter(()))
    monkeypatch.setattr(ach, "_peoples_choice", lambda user: iter(()))

    def spy(name):
        def run(user, ids):
            seen[name] = set(ids)
            return iter(())
        return run

    monkeypatch.setattr(ach, "_roles", spy("roles"))
    monkeypatch.setattr(ach, "_speaking", spy("speaking"))
    ach.derived_achievements(ada)
    expected = {m.makerspace_id for m in ada.makerspace_memberships.all()}
    assert seen["roles"] == seen["speaking"] == expected
