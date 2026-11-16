"""Browser and attested native machine creators contend for one shared slot."""
import pytest
from django.db import connection
from django.urls import reverse

from apps.machines.models import Machine, MachineType
from tests.inventory.test_creator_limit_concurrency_cx7 import callers
from tests.limits_0120.concurrency_helpers_cx7 import race_posts
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
def test_two_machine_http_creates_at_last_slot_have_one_exact_refusal(surface, settings, monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    settings.MANAGED_PLANS_ENABLED = False
    space = make_space("cx7-machine-api-race")
    pair = callers(space, surface, settings, monkeypatch)
    machine_type = MachineType.objects.create(makerspace=space, slug="quota-type", name="Quota type")
    space.resource_limit_overrides = {"machines": 1}
    space.save(update_fields=["resource_limit_overrides"])
    results = race_posts(pair, reverse("admin-machines", kwargs={"makerspace_id": space.pk}),
                         [{"machine_type_id": machine_type.pk, "name": name} for name in ("A", "B")])
    assert sorted(status for status, _ in results) == [201, 400]
    assert [body["code"] for status, body in results if status == 400] == ["limit_reached"]
    assert Machine.objects.filter(makerspace=space, is_active=True).count() == 1
