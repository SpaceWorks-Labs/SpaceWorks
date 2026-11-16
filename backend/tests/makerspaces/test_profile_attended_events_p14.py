"""Phase 1 -- opt-in publication of recently attended events on a maker profile.

`is_visible` consents to publishing the fields the member typed into the profile form.
Attendance history is neither typed by them nor part of that form, so it rides on its own
flag: attaching it to `is_visible` would disclose new information about already-visible
profiles with no new member action.

The payload-contract and audit cases live in `test_profile_attended_payload_p14.py`.
"""

import pytest

from apps.events.models import EventRegistration
from apps.makerspaces import profile_services
from apps.makerspaces.models import MakerspaceMembership, MakerspaceRole
from tests.makerspaces.attendance_helpers import (
    attend,
    make_space,
    member,
    publish,
)

pytestmark = pytest.mark.django_db


# --- consent -----------------------------------------------------------------------


def test_the_flag_defaults_to_on_since_profiles_are_open_by_default():
    """Decision 303a superseded the opt-in: every section defaults ON at platform level."""
    space = make_space()
    m = member(space)

    profile = profile_services.profile_for(m)

    assert profile.show_events is True


def test_a_member_who_switches_the_events_section_off_publishes_no_attendance_list():
    """Each section has its own switch: hiding this one withdraws the list, not the profile."""
    space = make_space()
    m = member(space)
    attend(m, "Laser night")
    profile_services.save_profile(m, {"is_visible": True, "show_attended_events": False})

    activity = profile_services.profile_activity(m)

    assert activity["events_attended"] == 1
    assert "recent_attended_events" not in activity


def test_setting_the_flag_publishes_the_list():
    space = make_space()
    m = member(space)
    attend(m, "Laser night")
    publish(m)

    activity = profile_services.profile_activity(m)

    assert [row["title"] for row in activity["recent_attended_events"]] == ["Laser night"]


def test_clearing_the_flag_withdraws_the_list_again():
    space = make_space()
    m = member(space)
    attend(m, "Laser night")
    publish(m)
    publish(m, attended=False)

    assert "recent_attended_events" not in profile_services.profile_activity(m)


# --- the list itself ---------------------------------------------------------------


def test_list_is_newest_first_and_carries_only_id_title_and_start():
    space = make_space()
    m = member(space)
    attend(m, "Older", days_ago=10)
    attend(m, "Newer", days_ago=2)
    publish(m)

    rows = profile_services.profile_activity(m)["recent_attended_events"]

    assert [row["title"] for row in rows] == ["Newer", "Older"]
    assert set(rows[0]) == {"id", "title", "starts_at"}


def test_list_is_capped_while_the_count_stays_truthful():
    """The cap is why the key says "recent" -- it must never read as a full history."""
    space = make_space()
    m = member(space)
    for index in range(25):
        attend(m, f"Event {index}", days_ago=index + 1)
    publish(m)

    activity = profile_services.profile_activity(m)

    assert len(activity["recent_attended_events"]) == 20
    assert activity["events_attended"] == 25


def test_events_sharing_a_start_time_order_deterministically():
    """Without an id tiebreaker the cap could return a different subset per request."""
    space = make_space()
    m = member(space)
    for index in range(3):
        attend(m, f"Simultaneous {index}", days_ago=5)
    publish(m)

    first = [r["id"] for r in profile_services.profile_activity(m)["recent_attended_events"]]
    second = [r["id"] for r in profile_services.profile_activity(m)["recent_attended_events"]]

    assert first == second
    assert first == sorted(first, reverse=True)


def test_only_attended_registrations_appear():
    space = make_space()
    m = member(space)
    attend(m, "Went", status=EventRegistration.Status.ATTENDED)
    attend(m, "Signed up", status=EventRegistration.Status.REGISTERED)
    attend(m, "Backed out", status=EventRegistration.Status.CANCELLED)
    publish(m)

    activity = profile_services.profile_activity(m)

    assert [row["title"] for row in activity["recent_attended_events"]] == ["Went"]
    assert activity["events_attended"] == 1
    # Cancellations are excluded from the registered count; the signup is not.
    assert activity["events_registered"] == 2


def test_an_email_only_registration_never_attaches_to_a_profile():
    """`member` is nullable, and matching on email would credit the wrong person.

    A shared household address is enough to attach one person's attendance to another's
    published profile, so the link must be the account and nothing else.
    """
    space = make_space()
    m = member(space)
    attend(m, "Anonymous walk-in", linked=False)
    publish(m)

    activity = profile_services.profile_activity(m)

    assert activity["events_attended"] == 0
    assert activity["recent_attended_events"] == []


def test_another_members_attendance_never_appears():
    space = make_space()
    mine, theirs = member(space, "mine"), member(space, "theirs")
    attend(theirs, "Their workshop")
    publish(mine)

    assert profile_services.profile_activity(mine)["recent_attended_events"] == []


def test_attendance_aggregates_over_spaces_the_member_belongs_to_but_never_others():
    """Decision 304c: the profile is global, so attendance from the person's own spaces appears;
    a space they are NOT an active member of never does (303c)."""
    here, elsewhere = make_space("here"), make_space("elsewhere")
    outsider_space = make_space("not-mine")
    mine = member(here, "mine")
    other_membership = MakerspaceMembership.objects.create(
        user=mine.user, makerspace=elsewhere,
        role=MakerspaceMembership.Role.CUSTOM,
        assigned_role=MakerspaceRole.objects.get(makerspace=elsewhere, slug="member"),
        status="active",
    )
    attend(other_membership, "Elsewhere night")
    stranger_membership = member(outsider_space, "someone")
    attend(stranger_membership, "Outsider night")
    from apps.events.models import EventRegistration as Reg
    Reg.objects.filter(event__title="Outsider night").update(member=mine.user)
    publish(mine)

    titles = [r["title"] for r in profile_services.profile_activity(mine)["recent_attended_events"]]
    assert titles == ["Elsewhere night"]
