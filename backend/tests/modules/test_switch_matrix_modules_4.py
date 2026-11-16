"""SWITCH-MATRIX 1 (shard 5/5): one fast case per (module, route the module gates).

The cases come from the committed route snapshot (`switch_matrix_snapshot.json`, kept honest by the snapshot guard):
with ONLY that module (and what requires it) off every other module is on, the route must answer exactly what the
core-only crawl recorded (typed gate: 404 `module_disabled` naming an off module; a dedicated surface: its own 404);
switched on again it must answer exactly its all-on baseline status and never `module_disabled`.
"""

import pytest

from tests.modules.switch_matrix_helpers import (
    MODULE_KEYS, case_id, dependents_closure, fill, live_space, module_cases, probe, root_client, route_map,
)

pytestmark = pytest.mark.django_db
CASES = module_cases(4, 5)


@pytest.mark.parametrize("case", CASES, ids=[case_id(c) for c in CASES])
def test_module_off_refuses_the_route_and_on_restores_it(case):
    key, route = case
    state, client = route_map(), root_client()
    off_set = {key} | dependents_closure(key)
    space = live_space("sx-case", set(MODULE_KEYS) - off_set)
    url = fill(route[1], space)

    status, code, named = probe(client, route[0], url)
    if route in state["typed"]:
        assert (status, code) == (404, "module_disabled"), (route, status, code)
        assert named in off_set, f"{route} refused naming {named}, which is on"
    else:
        assert (status, code) == tuple(state["cold"][route][:2]), (route, status, code)

    space.enabled_modules = sorted(set(space.enabled_modules) | off_set)
    space.save(update_fields=["enabled_modules"])
    status, code, _named = probe(client, route[0], url)
    assert status == state["base"][route][0], f"on again: {route} answers {status}, baseline {state['base'][route][0]}"
    assert code != "module_disabled"
