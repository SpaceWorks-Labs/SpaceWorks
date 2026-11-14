"""Bookable-space create and clone HTTP surfaces enforce their inclusive last slot."""
import pytest
from django.db import connection
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.bookings.models import BookableSpace
from tests.inventory.test_creator_limit_concurrency_cx7 import callers
from tests.limits_0120.concurrency_helpers_cx7 import race_posts
from tests.return_helpers import make_space

pytestmark = [pytest.mark.django_db, pytest.mark.area_bookings]


def scenario(kind):
    space = make_space("cx7-bookable-creator")
    space.enabled_modules = sorted(set(space.enabled_modules) | {"bookings"})
    space.enabled_features = sorted(set(space.enabled_features) | {"bookings.clone"})
    space.resource_limit_overrides = {"bookable_spaces": 1 if kind == "create" else 2}
    space.save(update_fields=["enabled_modules", "enabled_features", "resource_limit_overrides"])
    if kind == "clone":
        source = BookableSpace.objects.create(makerspace=space, name="Source", kind="other")
        url = reverse("admin-bookable-space-clone", kwargs={"pk": source.pk})
        bodies = [{}, {}]
    else:
        url = reverse("admin-bookable-space-list-create", kwargs={"makerspace_id": space.pk})
        bodies = [{"name": name, "kind": "other"} for name in ("First", "Second")]
    return space, url, bodies


@pytest.mark.parametrize("kind", ["create", "clone"])
@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
def test_bookable_creator_max_then_next_refusal_preserves_configuration(kind, surface, settings, monkeypatch):
    settings.MANAGED_PLANS_ENABLED = False
    space, url, bodies = scenario(kind)
    caller = callers(space, surface, settings, monkeypatch)[0]
    assert caller.post(url, bodies[0], format="json").status_code == 201
    before = list(BookableSpace.objects.filter(makerspace=space).order_by("pk").values())
    audits = list(AuditLog.objects.filter(makerspace=space).order_by("pk").values())
    refused = caller.post(url, bodies[1], format="json")
    assert (refused.status_code, refused.json()["code"]) == (409, "bookable_spaces_quota_reached")
    assert list(BookableSpace.objects.filter(makerspace=space).order_by("pk").values()) == before
    assert list(AuditLog.objects.filter(makerspace=space).order_by("pk").values()) == audits


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("kind", ["create", "clone"])
@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
def test_bookable_creators_racing_at_last_slot_admit_one(kind, surface, settings, monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    settings.MANAGED_PLANS_ENABLED = False
    space, url, bodies = scenario(kind)
    results = race_posts(callers(space, surface, settings, monkeypatch), url, bodies)
    assert sorted(status for status, _ in results) == [201, 409]
    assert [body["code"] for status, body in results if status == 409] == ["bookable_spaces_quota_reached"]
    assert BookableSpace.objects.filter(makerspace=space).count() == (1 if kind == "create" else 2)
