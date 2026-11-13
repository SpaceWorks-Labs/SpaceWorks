"""Inventory D16: the public expected-back date is opt-in, date-only and never names a borrower."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.hardware_requests.models import HardwareRequest
from tests.return_helpers import make_issued_request, make_member, make_product, make_space

pytestmark = pytest.mark.django_db


def public_rows(client, space):
    return {row["name"]: row for row in client.get(f"/api/v1/public/{space.slug}/inventory/").json()["results"]}


def setup(slug, *, feature=True, opt_in=True):
    space = make_space(slug)
    space.public_site_enabled = space.public_inventory_enabled = True
    features = set(space.enabled_features or [])
    if feature:
        features.add("inventory.expected_back")
    space.enabled_features = sorted(features)
    space.save(update_fields=["public_site_enabled", "public_inventory_enabled", "enabled_features"])
    staff = make_member(f"{slug}-sm", space)
    product = make_product(space, name="Router", available_quantity=1, total_quantity=1, is_public=True,
                           public_show_expected_back=opt_in)
    loan = make_issued_request(space, staff, [(product, 1)])
    due = timezone.now() + timedelta(days=4)
    HardwareRequest.objects.filter(pk=loan.pk).update(return_due_at=due)
    return space, due


def test_opted_in_unavailable_item_shows_only_a_date(client):
    space, due = setup("expected-on")
    row = public_rows(client, space)["Router"]
    from zoneinfo import ZoneInfo
    assert row["expected_back_on"] == timezone.localtime(due, ZoneInfo(space.timezone)).date().isoformat()
    body = str(row)
    assert "requester" not in body and "return_due_at" not in body


@pytest.mark.parametrize("feature,opt_in", [(False, True), (True, False)])
def test_switch_or_opt_in_off_shows_nothing(client, feature, opt_in):
    space, _ = setup(f"expected-off-{feature}-{opt_in}".lower(), feature=feature, opt_in=opt_in)
    assert public_rows(client, space)["Router"]["expected_back_on"] is None
