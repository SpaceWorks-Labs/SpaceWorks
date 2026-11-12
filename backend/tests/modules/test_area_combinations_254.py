"""Decision 254: every combination of the main areas yields a sensible space.

The single-area families have their own tests (test_family_*_only.py). This pins every COMBINATION of
Inventory, Machines, Events and Bookings (with and without Membership) as the installer and first-run wizard
build it (`setup_areas.modules_for` / `features_for`): the tenant bootstrap the public site and the console
navigation are drawn from serves exactly the chosen areas, has at least one workflow to show (no empty site),
and the Space Manager's dashboard answers.
"""
from itertools import combinations

import pytest
from django.urls import reverse

from apps.makerspaces.models import Makerspace
from apps.makerspaces.platform import bootstrap_payload
from apps.makerspaces.setup_areas import features_for, modules_for
from tests.modules.family_helpers import account, client

pytestmark = pytest.mark.django_db

MAIN = ("inventory", "machines", "events", "bookings")
COMBOS = [set(combo) for size in range(1, len(MAIN) + 1) for combo in combinations(MAIN, size)]
CASES = [(combo, membership) for combo in COMBOS for membership in (False, True)]


def _space(areas):
    slug = "combo-" + "-".join(sorted(areas))
    modules = modules_for(areas)
    return Makerspace.objects.create(name=slug, slug=slug, enabled_modules=sorted(modules),
                                     enabled_features=features_for(areas, modules))


@pytest.mark.parametrize(("combo", "membership"), CASES,
                         ids=["+".join(sorted(c)) + ("+membership" if m else "") for c, m in CASES])
def test_each_area_combination_serves_exactly_its_areas_and_a_working_home(combo, membership):
    areas = set(combo) | ({"membership"} if membership else set())
    space = _space(areas)

    body = bootstrap_payload(space)
    modules, features = set(body["modules"]), set(body["features"])
    assert body["workflows"], "every combination has something to show on the public site"

    assert ("loans.enabled" in features) is ("inventory" in areas)
    assert ("catalog" in body["workflows"]) is ("inventory" in areas)
    for area in ("machines", "events", "bookings"):
        assert (area in modules) is (area in areas), area
    assert ("membership" in modules) is membership

    manager = account(f"{space.slug}-sa"[:30], staff=True)
    dashboard = client(manager).get(reverse("operations-dashboard", args=[space.pk]))
    assert dashboard.status_code == 200, dashboard.data
