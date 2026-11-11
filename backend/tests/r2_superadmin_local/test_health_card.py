"""#185 item 7: the per-space health card's numbers come from their own sources."""

import uuid

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.audit import services as audit
from apps.backup.models_drill import RestoreDrillReport
from apps.makerspaces.models_security import MakerspaceSecurityLock
from apps.space_controls import health

from .helpers import api, control, manager, member, space, superadmin

pytestmark = pytest.mark.django_db
BASE = "/api/v1/admin/platform/space-health"


@pytest.fixture
def world(settings):
    settings.PLATFORM_DOMAIN_SUFFIX = ".space-works.test"
    settings.MANAGED_RESOURCE_LIMITS = {**settings.MANAGED_RESOURCE_LIMITS, "members": 4}
    lab = space()
    root, boss = superadmin(), manager(lab)
    people = [member(lab, f"person-{index}") for index in range(3)]
    return type("World", (), dict(lab=lab, root=root, boss=boss, people=people))


def test_card_numbers(world):
    blocked = world.people[0]
    blocked.access_status = User.AccessStatus.RESTRICTED
    blocked.save(update_fields=["access_status"])
    MakerspaceSecurityLock.objects.create(makerspace=world.lab, key="security.staff_mfa_required", floor=True,
                                          locked_by=world.root)
    RestoreDrillReport.objects.create(makerspace=world.lab, makerspace_id_snapshot=world.lab.pk,
                                      archive_id_snapshot=uuid.uuid4(), outcome="passed",
                                      finished_at=timezone.now())
    audit.record(world.root, "makerspace.updated", makerspace=world.lab, target=world.lab, meta={})
    card = api(world.root).get(f"{BASE}/{world.lab.pk}").json()
    assert card["state"] == "active" and card["modules"] == sorted(world.lab.enabled_modules)
    members = next(row for row in card["usage"]["resources"] if row["key"] == "members")
    assert members["used"] == 2 and members["limit"] == 4 and members["percent"] == 50.0
    assert card["usage_peak_percent"] >= 50.0
    assert card["security"] == {"blocked_accounts": 1, "locked_settings": 1}
    assert card["backups"]["last_drill"]["outcome"] == "passed"
    assert card["last_activity_at"] is not None
    assert [row["user_id"] for row in card["managers"]] == [world.boss.pk]
    assert "plan" not in card  # the managed limiter is off
    assert isinstance(card["problems"], list) and card["open_issues"] == sum(
        1 for row in card["problems"] if row["status"] != "ok")


def test_state_labels_and_filter(world):
    other = space("paused-lab")
    control(world.root, other, "suspend", {"reason": "Paused for a review of reports."})
    third = space("frozen-lab")
    control(world.root, third, "read-only", {"reason": "Frozen while the invoice is settled."})
    listing = api(world.root).get(BASE).json()
    states = {row["slug"]: row["state"] for row in listing["results"]}
    assert states == {"north-lab": "active", "paused-lab": "suspended", "frozen-lab": "read_only"}
    only = api(world.root).get(BASE, {"state": "suspended"}).json()["results"]
    assert [row["slug"] for row in only] == ["paused-lab"]
    assert only[0]["suspended"]["reason"].startswith("Paused")
    assert api(world.root).get(BASE, {"search": "frozen"}).json()["count"] == 1


def test_archived_and_scheduled_labels(world):
    control(world.root, world.lab, "archive")
    world.lab.refresh_from_db()
    assert health.card(world.lab)["state"] == "archived"
    control(world.root, world.lab, "schedule", {"purge_grace_days": 30})
    assert health.card(world.lab)["state"] == "scheduled"


def test_only_the_superadmin_reads_health(world):
    assert api(world.boss).get(BASE).status_code == 403
    assert api(world.boss).get(f"{BASE}/{world.lab.pk}").status_code == 403
