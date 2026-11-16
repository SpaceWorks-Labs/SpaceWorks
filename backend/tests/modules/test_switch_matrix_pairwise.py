"""SWITCH-MATRIX 2: every PAIR of module keys in every on/off combination, plus the dependency chains.

`pairwise_rows()` builds a deterministic all-pairs covering array over every optional module key (so a new key is
included automatically). Each row is a valid tenant (every module's `requires_modules` closure is on). Impossible
pairs (one module on while the module it requires is off) are listed with their reason and asserted refused.

Per row: the enabled set serves its routes (no 5xx, never `module_disabled` for a module that is on), the disabled set
refuses with `module_disabled` naming a module that is off, and routes no switch owns answer exactly as in the
all-on baseline (so no module's absence crashes or changes an unrelated surface: events off while machines on,
payments off while membership/bookings/events/shop charge ...).
"""

import pytest
from django.core.exceptions import ValidationError

from apps.makerspaces.module_install import ModuleInstallError, install_module, uninstall_module
from apps.makerspaces.module_registry import BY_KEY
from tests.modules.switch_matrix_helpers import (
    CORE, MODULE_KEYS, MULTI_GATED, OPTIONAL, closure_on, feasible_pairs, fill, live_space, pairwise_rows, probe, root_client,
    route_map,
)

pytestmark = pytest.mark.django_db

ROWS = pairwise_rows()
PER_MODULE = 2
UNOWNED_SAMPLE = 40


def _sample(gates, key, base):
    owned = sorted(r for r, group in gates.items() if key in group and r not in MULTI_GATED)
    served = [r for r in owned if base[r][0] < 400] or owned
    return served[:PER_MODULE]


def test_the_covering_array_covers_every_feasible_pair_and_every_row_is_a_valid_tenant():
    feasible, impossible = feasible_pairs()
    covered = set()
    for on in ROWS:
        assert closure_on(on) == set(on), "a row switches a module on without what it requires"
        covered |= {(a, int(a in on), b, int(b in on)) for i, a in enumerate(OPTIONAL) for b in OPTIONAL[i + 1:]}
    assert feasible <= covered, f"{len(feasible - covered)} feasible pairs uncovered"
    assert not (set(impossible) & covered), "an impossible pair appears in a row"
    assert len(ROWS) <= 40, len(ROWS)
    assert all("requires" in reason for reason in impossible.values())


@pytest.mark.parametrize("index", range(len(ROWS)))
def test_row_enabled_set_works_and_disabled_set_refuses(index):
    state, on = route_map(), set(ROWS[index])
    client = root_client()
    space = live_space(f"sx-pw-{index}", on)
    off = set(OPTIONAL) - on
    problems, checked = [], set(MULTI_GATED)
    for key in OPTIONAL:
        checked |= set(_sample(state["gates"], key, state["base"]))
    for route in sorted(checked):
        status, code, named = probe(client, route[0], fill(route[1], space))
        group = state["gates"].get(route, frozenset())
        refused_expected = MULTI_GATED[route] <= off if route in MULTI_GATED else bool(group & off)
        if refused_expected:
            typed = route in state["typed"]
            if status != 404 or (typed and (code != "module_disabled" or named not in off)) or (not typed and (status, code) != state["cold"][route][:2]):
                problems.append((route, "should be refused by an off module", status, code, named))
        elif status != state["base"][route][0] or code == "module_disabled":
            problems.append((route, "enabled set differs from all-on", status, code, named, state["base"][route]))
    ungated = sorted(r for r, v in state["base"].items() if r not in state["gates"] and r not in state["candidates"]
                     and r not in state["features"] and r not in MULTI_GATED and v[0] < 500)
    for route in ungated[:: max(1, len(ungated) // UNOWNED_SAMPLE)][:UNOWNED_SAMPLE]:
        status = probe(client, route[0], fill(route[1], space))
        if status[0] != state["base"][route][0] and status[0] != 429:
            problems.append((route, "unrelated surface changed", state["base"][route][0], status))
    assert not problems, "\n" + "\n".join(map(str, problems[:15]))


# --- dependency chains ---------------------------------------------------------------------------------------


CHAINS = sorted((child, parent) for child, d in BY_KEY.items() for parent in d.requires_modules)


def test_there_are_dependency_chains_to_test():
    assert CHAINS


@pytest.mark.parametrize("child,parent", CHAINS)
def test_a_child_cannot_stay_on_when_its_parent_is_switched_off(child, parent):
    space = live_space(f"sx-dep-{child}", closure_on({child}))
    assert child in space.enabled_modules and parent in space.enabled_modules
    with pytest.raises((ModuleInstallError, ValidationError)):
        uninstall_module(space, parent)
    space.refresh_from_db()
    assert parent in space.enabled_modules and child in space.enabled_modules


@pytest.mark.parametrize("child,parent", CHAINS)
def test_installing_a_child_without_its_parent_pulls_the_parent_in(child, parent):
    space = live_space(f"sx-pull-{child}", set())
    assert parent not in space.enabled_modules
    install_module(space, child)
    space.refresh_from_db()
    assert child in space.enabled_modules and parent in space.enabled_modules


@pytest.mark.parametrize("child,parent", CHAINS)
def test_child_off_then_parent_off_then_back_on_in_order(child, parent):
    space = live_space(f"sx-order-{child}", closure_on({child}))
    uninstall_module(space, child)
    uninstall_module(space, parent)
    space.refresh_from_db()
    assert child not in space.enabled_modules and parent not in space.enabled_modules
    install_module(space, parent)
    install_module(space, child)
    space.refresh_from_db()
    assert {child, parent} <= set(space.enabled_modules)


def test_core_modules_cannot_be_switched_off():
    space = live_space("sx-core", MODULE_KEYS)
    for key in sorted(CORE):
        with pytest.raises((ModuleInstallError, ValidationError)):
            uninstall_module(space, key)
    space.refresh_from_db()
    assert CORE <= set(space.enabled_modules)
