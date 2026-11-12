"""Decision 325a: the "inventory highlights" and "sponsors" display panels reuse the public site's rules."""
import json
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.inventory.models import PublicAvailabilityMode
from apps.payments.donations.models import Sponsor
from apps.presence.display_panels_extra import inventory_highlights, sponsors_wall
from tests.return_helpers import make_product

pytestmark = pytest.mark.django_db


def _open_catalogue(space):
    space.public_site_enabled = True
    space.public_inventory_enabled = True
    space.enabled_modules = sorted(set(space.enabled_modules) | {"public_inventory", "request_workflow"})
    space.enabled_features = sorted(set(space.enabled_features) | {"loans.enabled"})
    space.save(update_fields=["public_site_enabled", "public_inventory_enabled", "enabled_modules", "enabled_features"])


def _sponsors_on(space):
    space.enabled_features = sorted(set(space.enabled_features) | {"finance.sponsors"})
    space.save(update_fields=["enabled_features"])


def test_highlights_follow_public_visibility_and_availability_modes_and_never_leak_locations(lane):
    space = lane.space
    _open_catalogue(space)
    make_product(space, "Exact item", public_availability_mode=PublicAvailabilityMode.EXACT_COUNT,
                 show_public_count=True, storage_location="SECRET-SHELF-1", issued_quantity=9, total_quantity=20)
    make_product(space, "Gated count", public_availability_mode=PublicAvailabilityMode.EXACT_COUNT,
                 show_public_count=False, issued_quantity=8, total_quantity=20)
    make_product(space, "Hidden count", public_availability_mode=PublicAvailabilityMode.HIDDEN, issued_quantity=7, total_quantity=20)
    make_product(space, "Private item", is_public=False)
    make_product(space, "Archived item", is_archived=True)
    make_product(space, "Consumable item", is_consumable=True)
    panel = inventory_highlights(space)
    names = [item["name"] for item in panel["items"]]
    assert names == ["Exact item", "Gated count", "Hidden count"]
    by_name = {item["name"]: item["availability"] for item in panel["items"]}
    assert by_name["Exact item"]["mode"] == "exact_count" and by_name["Exact item"]["count"] == 10
    assert by_name["Gated count"] == {"mode": "status_only", "label": "Available"}
    assert by_name["Hidden count"] is None
    assert "SECRET-SHELF-1" not in json.dumps(panel)
    assert set(panel["items"][0]) == {"name", "category", "image_url", "availability"}


def test_highlights_are_absent_while_the_public_catalogue_is_closed_or_empty(lane):
    assert inventory_highlights(lane.space) is None
    _open_catalogue(lane.space)
    assert inventory_highlights(lane.space) is None  # open but nothing public yet
    make_product(lane.space, "Visible")
    lane.space.public_inventory_enabled = False
    lane.space.save(update_fields=["public_inventory_enabled"])
    assert inventory_highlights(lane.space) is None


def test_sponsor_wall_shows_only_live_wall_sponsors_with_public_fields(lane):
    space = lane.space
    assert sponsors_wall(space) is None  # finance.sponsors is off
    _sponsors_on(space)
    today = timezone.localdate()
    Sponsor.objects.create(makerspace=space, name="Acme", website_url="https://acme.example", blurb="Thanks")
    Sponsor.objects.create(makerspace=space, name="Hidden", show_on_wall=False)
    Sponsor.objects.create(makerspace=space, name="Archived", archived_at=timezone.now())
    Sponsor.objects.create(makerspace=space, name="Ended", ends_on=today - timedelta(days=1))
    panel = sponsors_wall(space)
    assert [row["name"] for row in panel["sponsors"]] == ["Acme"]
    assert set(panel["sponsors"][0]) == {"name", "tier", "logo_url"}


def test_screen_state_carries_the_new_panels_only_when_chosen(lane, settings):
    settings.PUBLIC_APP_BASE_URL = "https://spaces.example.test"  # the secret-bearing link needs an origin
    _open_catalogue(lane.space)
    _sponsors_on(lane.space)
    make_product(lane.space, "Shown on screen")
    Sponsor.objects.create(makerspace=lane.space, name="Acme")
    admin = lane.client(lane.staff)
    base = f"/api/v1/admin/makerspace/{lane.space.pk}/presence-displays"
    made = admin.post(f"{base}/link", {"panels": ["here_now"]}, format="json").json()
    token = made["url"].split("#k=")[1]
    state = lane.client().get(f"/api/v1/space-displays/{token}/state/").json()
    assert state["inventory_highlights"] is None and state["sponsors"] is None
    patched = admin.patch(f"{base}/{made['id']}", {"panels": ["inventory_highlights", "sponsors"]}, format="json")
    assert patched.status_code == 200, patched.content
    state = lane.client().get(f"/api/v1/space-displays/{token}/state/").json()
    assert [item["name"] for item in state["inventory_highlights"]["items"]] == ["Shown on screen"]
    assert [row["name"] for row in state["sponsors"]["sponsors"]] == ["Acme"]
    assert admin.patch(f"{base}/{made['id']}", {"panels": ["inventory_highlights", "nope"]}, format="json").status_code == 400
