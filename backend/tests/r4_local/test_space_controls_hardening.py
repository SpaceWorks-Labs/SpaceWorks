"""R4 security: health-card PII masking and the typed slug on a scheduled purge. Local only."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts import pii_access
from apps.accounts.pii_presentation import MASK
from apps.space_controls.models import SpaceControlState
from tests.r2_superadmin_local.helpers import api, control, manager, space, superadmin

pytestmark = pytest.mark.django_db
BASE = "/api/v1/admin/platform/space-health"
WHY = "Checking a disputed membership for the space"


@pytest.fixture
def world(mailbox):
    lab, other = space(), space("south-lab")
    root, boss = superadmin(), manager(lab)
    return type("World", (), dict(lab=lab, other=other, root=root, boss=boss))


def _managers(world, url):
    return api(world.root).get(url).json()["managers"]


def test_manager_pii_is_masked_without_a_window(world):
    detail = _managers(world, f"{BASE}/{world.lab.pk}")
    assert detail[0]["user_id"] == world.boss.pk
    assert detail[0]["email"] == MASK and detail[0]["name"] == MASK
    listing = api(world.root).get(BASE).json()["results"]
    row = next(card for card in listing if card["id"] == world.lab.pk)
    assert row["managers"][0]["email"] == MASK
    after_control = control(world.root, world.lab, "suspend", {"reason": "Paused for a review of reports."})
    assert after_control.json()["managers"][0]["email"] == MASK


def test_window_on_the_space_unmasks_only_that_space(world):
    pii_access.open_grant(world.root, world.other, WHY)
    assert _managers(world, f"{BASE}/{world.lab.pk}")[0]["email"] == MASK
    pii_access.open_grant(world.root, world.lab, WHY)
    shown = _managers(world, f"{BASE}/{world.lab.pk}")[0]
    assert shown["email"] == world.boss.email and shown["name"] != MASK


def test_schedule_needs_the_typed_slug(world):
    body = {"purge_grace_days": 30, "archive_on": (timezone.now() + timedelta(days=10)).isoformat()}
    missing = api(world.root).post(f"/api/v1/admin/platform/spaces/{world.lab.pk}/schedule", body, format="json")
    assert missing.status_code == 400
    wrong = control(world.root, world.lab, "schedule", {**body, "confirm_slug": "south-lab"})
    assert wrong.status_code == 400 and "slug_mismatch" in wrong.content.decode()
    assert not SpaceControlState.objects.filter(makerspace=world.lab, purge_due_at__isnull=False).exists()
    assert not SpaceControlState.objects.filter(makerspace=world.lab, archive_on__isnull=False).exists()
    right = control(world.root, world.lab, "schedule", {**body, "confirm_slug": "north-lab"})
    assert right.status_code == 200, right.content
