"""#185 item 6: announcements -- banner + email, targeting, schedule, cancel, audited."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.space_controls.announcements import send_due_emails
from apps.space_controls.models import PlatformAnnouncement

from .helpers import api, manager, member, space, superadmin

pytestmark = pytest.mark.django_db
BASE = "/api/v1/admin/platform/announcements"


@pytest.fixture
def world(mailbox):
    north, south, west = space("north-lab"), space("south-lab"), space("west-lab")
    return type("World", (), dict(
        north=north, south=south, west=west, root=superadmin(), mail=mailbox,
        north_boss=manager(north), south_boss=manager(south), west_boss=manager(west),
        north_member=member(north),
    ))


def announce(world, **fields):
    body = {"title": "Maintenance", "body": "Saturday 02:00-03:00 UTC.", "severity": "maintenance",
            "audience": "all_spaces", "send_email": True, **fields}
    response = api(world.root).post(BASE, body, format="json")
    assert response.status_code == 201, response.content
    return response.json()


def banner_ids(user):
    return [row["id"] for row in api(user).get("/api/v1/platform-notices").json()["announcements"]]


def test_all_spaces_reaches_every_staff_member_but_not_members_by_default(world):
    row = announce(world)
    assert row["status"] == "live"
    for user in (world.north_boss, world.south_boss, world.west_boss, world.root):
        assert banner_ids(user) == [row["id"]]
    assert banner_ids(world.north_member) == []
    shown = announce(world, title="Policy", severity="policy", show_to_members=True)
    assert banner_ids(world.north_member) == [shown["id"]]


def test_selected_spaces_only(world):
    row = announce(world, audience="selected_spaces", makerspace_ids=[world.north.pk])
    assert [space["id"] for space in row["makerspaces"]] == [world.north.pk]
    assert banner_ids(world.north_boss) == [row["id"]]
    assert banner_ids(world.south_boss) == []
    bad = api(world.root).post(BASE, {"title": "x", "body": "y", "audience": "selected_spaces"}, format="json")
    assert bad.status_code == 400


def test_notices_name_only_the_viewers_own_spaces(world):
    # #195: a viewer never learns which OTHER spaces an announcement targets, and member pages
    # get only what reaches them as a member.
    announce(world, audience="selected_spaces", makerspace_ids=[world.north.pk, world.south.pk])
    row = api(world.north_boss).get("/api/v1/platform-notices").json()["announcements"][0]
    assert row["makerspace_ids"] == [world.north.pk] and row["member_makerspace_ids"] == []
    announce(world, title="Policy", severity="policy", show_to_members=True)
    member_view = api(world.north_member).get("/api/v1/platform-notices").json()["announcements"]
    assert [(item["title"], item["member_makerspace_ids"]) for item in member_view] == [("Policy", [world.north.pk])]


def test_schedule_window_and_cancel(world):
    later = announce(world, starts_at=(timezone.now() + timedelta(days=1)).isoformat())
    assert later["status"] == "scheduled" and banner_ids(world.north_boss) == []
    live = announce(world)
    cancelled = api(world.root).post(f"{BASE}/{live['id']}/cancel", {}, format="json").json()
    assert cancelled["status"] == "cancelled" and banner_ids(world.north_boss) == []
    assert api(world.root).post(f"{BASE}/{live['id']}/cancel", {}, format="json").status_code == 409
    assert AuditLog.objects.filter(action="space_control.announcement_cancelled").count() == 1


def test_email_goes_once_to_the_targeted_space_managers(world):
    announce(world, audience="selected_spaces", makerspace_ids=[world.north.pk, world.south.pk])
    assert send_due_emails() == {"announcements": 1}
    recipients = sorted(message.to[0] for message in world.mail)
    assert recipients == sorted([world.north_boss.email, world.south_boss.email])
    assert send_due_emails() == {"announcements": 0}
    row = PlatformAnnouncement.objects.get()
    assert row.email_sent_at is not None and row.email_recipient_count == 2
    assert AuditLog.objects.get(action="space_control.announcement_emailed").meta == {"recipient_count": 2}


def test_only_the_superadmin_manages_announcements(world):
    assert api(world.north_boss).get(BASE).status_code == 403
    assert api(world.north_boss).post(BASE, {"title": "x", "body": "y"}, format="json").status_code == 403
    entry = announce(world)
    assert AuditLog.objects.get(action="space_control.announcement_created").meta["audience"] == "all_spaces"
    assert api(world.root).get(f"{BASE}/{entry['id']}").json()["title"] == "Maintenance"
