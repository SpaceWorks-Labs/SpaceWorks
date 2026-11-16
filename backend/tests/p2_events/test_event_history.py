"""Account-only attendee history and the staff member drawer Events block."""

import pytest

from apps.events.speaker_identity import assign_speaker
from apps.makerspaces.models import MakerspaceMembership
from tests.p2_events.helpers import account, client_for, event, make_member, make_staff, registration, space

pytestmark = pytest.mark.django_db


def test_account_only_attendee_reads_history_without_membership_module():
    home = space("hist-guest")  # no membership module installed
    assert "membership" not in home.enabled_modules
    guest = account("hist-guest-user")
    attended = event(home, days=-2, title="Attended")
    registration(attended, guest, status="attended")
    registration(event(home, title="Upcoming"), guest)
    response = client_for(guest).get(f"/api/v1/member/makerspaces/{home.pk}/event-history/")
    assert response.status_code == 200
    assert response.data["counts"] == {"registered": 2, "attended": 1, "cancelled": 0, "speaking": 0}
    assert {row["event"]["title"] for row in response.data["registrations"]} == {"Attended", "Upcoming"}
    assert "email" not in str(response.data)


def test_speaker_history_appears_in_the_speakers_own_history():
    home = space("hist-speaker")
    staff, member = make_staff(home), make_member(home, "hist-spk")
    talk = event(home, days=-1, title="Talk")
    assign_speaker(talk, actor=staff, user=member)
    response = client_for(member).get(f"/api/v1/member/makerspaces/{home.pk}/event-history/")
    assert response.status_code == 200 and response.data["counts"]["speaking"] == 1
    assert response.data["speaking"][0]["event"]["id"] == talk.pk and response.data["speaking"][0]["role"] == "speaker"


def test_revoked_member_and_stranger_are_refused():
    home = space("hist-revoked")
    member, stranger = make_member(home, "hist-rev"), account("hist-stranger")
    registration(event(home), member)
    MakerspaceMembership.objects.filter(user=member, makerspace=home).update(status="revoked")
    assert client_for(member).get(f"/api/v1/member/makerspaces/{home.pk}/event-history/").status_code == 403
    assert client_for(stranger).get(f"/api/v1/member/makerspaces/{home.pk}/event-history/").status_code == 403


def test_staff_drawer_block_needs_events_or_members_authority():
    home = space("hist-drawer")
    staff, member = make_staff(home), make_member(home, "hist-drawer-m")
    registration(event(home, days=-1), member, status="attended")
    url = f"/api/v1/admin/makerspaces/{home.pk}/members/{member.pk}/events/"
    response = client_for(staff).get(url)
    assert response.status_code == 200 and response.data["counts"]["attended"] == 1
    assert client_for(member).get(url).status_code == 403
    outsider = make_staff(space("hist-drawer-other"))
    assert client_for(outsider).get(url).status_code in (403, 404)
    stranger = account("hist-drawer-stranger")
    assert client_for(staff).get(f"/api/v1/admin/makerspaces/{home.pk}/members/{stranger.pk}/events/").status_code == 404
