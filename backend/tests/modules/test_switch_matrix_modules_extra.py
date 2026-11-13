"""SWITCH-MATRIX 1 (extra): routes two modules share, and refusals that do not name their capability."""

import pytest

from tests.modules.switch_matrix_helpers import (
    MODULE_KEYS, MULTI_GATED, dependents_closure, fill, live_space, probe, root_client, route_map,
)

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("route,group", sorted(MULTI_GATED.items(), key=str), ids=lambda v: str(v)[:80])
def test_a_route_two_modules_share_stays_served_until_both_are_off(route, group):
    client = root_client()
    first = sorted(group)[0]
    served = live_space("sx-multi-on", set(MODULE_KEYS) - {first} - dependents_closure(first))
    assert probe(client, route[0], fill(route[1], served))[0] == 200, "one module off must not refuse a shared route"
    off = set(group)
    for key in group:
        off |= dependents_closure(key)
    refused = live_space("sx-multi-off", set(MODULE_KEYS) - off)
    status, code, named = probe(client, route[0], fill(route[1], refused))
    assert (status, code) == (404, "module_disabled") and named in group, (status, code, named)


def test_routes_whose_refusal_does_not_name_their_capability_are_refused_exactly_with_none_on():
    state, client = route_map(), root_client()
    unnamed = state["features_unnamed"]
    assert unnamed, "expected the billing/finance routes that refuse without naming their capability"
    on = live_space("sx-unnamed-on", MODULE_KEYS)
    served = {r: v for r in unnamed for v in [probe(client, r[0], fill(r[1], on))] if v[1] == "feature_disabled"}
    assert not served, f"refused with every capability on: {served}"
    off = live_space("sx-unnamed-off", MODULE_KEYS, features=[])
    refused = {r: v for r in unnamed for v in [probe(client, r[0], fill(r[1], off))] if v[:2] != (404, "feature_disabled")}
    assert not refused, refused
