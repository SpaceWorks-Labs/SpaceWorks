"""SWITCH-MATRIX 1 (extra): routes two modules share, and refusals that do not name their capability."""

import pytest
from tests.modules.test_switch_matrix_on_responses import assert_reviewed_on

from tests.modules.switch_matrix_helpers import (
    LIVE_FEATURES, MODULE_KEYS, MULTI_GATED, MULTI_FEATURE_GATED, dependents_closure, fill, live_space, probe, root_client, route_map,
    run_unnamed_case,
)

pytestmark = pytest.mark.django_db
UNNAMED_ROUTES = route_map()["features_unnamed"]
assert UNNAMED_ROUTES, "expected the billing/finance routes that refuse without naming their capability"


@pytest.mark.parametrize("route,group", sorted(MULTI_GATED.items(), key=str), ids=lambda v: str(v)[:80])
def test_a_route_two_modules_share_stays_served_until_both_are_off(route, group):
    client = root_client()
    first = sorted(group)[0]
    served = live_space("sx-multi-on", set(MODULE_KEYS) - {first} - dependents_closure(first))
    assert_reviewed_on(route, probe(client, route[0], fill(route[1], served)))
    off = set(group)
    for key in group:
        off |= dependents_closure(key)
    refused = live_space("sx-multi-off", set(MODULE_KEYS) - off)
    status, code, named = probe(client, route[0], fill(route[1], refused))
    assert (status, code) == (404, "module_disabled") and named in group, (status, code, named)


@pytest.mark.parametrize("route", UNNAMED_ROUTES)
def test_routes_whose_refusal_does_not_name_their_capability_are_refused_exactly_with_none_on(route):
    space = live_space("sx-unnamed", MODULE_KEYS)
    run_unnamed_case(route, root_client(), space)


@pytest.mark.parametrize("route,group", sorted(MULTI_FEATURE_GATED.items()))
def test_either_wallet_capability_restores_the_shared_credentials_surface(route, group):
    client = root_client()
    space = live_space("sx-wallet-features", MODULE_KEYS, features=set(LIVE_FEATURES) - group)
    url = fill(route[1], space)
    assert probe(client, route[0], url)[:2] == (404, "feature_disabled")
    for key in sorted(group):
        space.enabled_features = sorted((set(LIVE_FEATURES) - group) | {key})
        space.save(update_fields=["enabled_features"])
        # PATCH {} is valid and preserves existing credentials. GET and PATCH are both shared.
        assert probe(client, route[0], url)[:2] == (200, None)
