"""SWITCH-MATRIX 1 (capabilities, shard 1/2): one fast case per (capability, route it gates).

With every module on and ONLY that capability (plus whatever requires it) off, the route answers exactly 404
`feature_disabled` naming a capability that is off; switched on again it never answers `feature_disabled`.
"""

import pytest

from apps.makerspaces.capabilities import FEATURES
from tests.modules.switch_matrix_helpers import (
    LIVE_FEATURES, MODULE_KEYS, case_id, feature_cases, fill, live_space, probe, root_client, route_map,
)

pytestmark = pytest.mark.django_db
CASES = feature_cases(0, 2)


def _requiring(key):
    out, grew = {key}, True
    while grew:
        grew = False
        for k, d in FEATURES.items():
            if k not in out and set(d.requires_features) & out:
                out.add(k)
                grew = True
    return out


@pytest.mark.parametrize("case", CASES, ids=[case_id(c) for c in CASES])
def test_capability_off_refuses_the_route_and_on_restores_it(case):
    key, route = case
    client, off_set = root_client(), _requiring(key)
    assert key in LIVE_FEATURES
    space = live_space("sx-fcase", MODULE_KEYS, features=set(LIVE_FEATURES) - off_set)
    url = fill(route[1], space)
    status, code, named = probe(client, route[0], url)
    assert (status, code) == (404, "feature_disabled") and named in off_set, (route, status, code, named)
    space.enabled_features = sorted(set(space.enabled_features) | off_set)
    space.save(update_fields=["enabled_features"])
    status, code, _named = probe(client, route[0], url)
    assert code != "feature_disabled" and status == route_map()["base"][route][0], (route, status, code)
