"""SWITCH-MATRIX: the committed route snapshot is complete and healthy (fast, no crawl).

Every API route (method + template) of the live URL conf must be in the snapshot, so a new route cannot slip past the
per-switch cases: if this fails, run `regen_switch_matrix.py` (see that file) and commit the new snapshot.
"""

import pytest

from tests.modules.switch_matrix_helpers import (
    LIVE_FEATURES, MODULE_KEYS, MULTI_GATED, OPTIONAL, TYPED_503, api_routes, route_map,
)

NO_ROUTE_MODULES = {
    "discord": "outbound channel; its installation routes ride `notifications`",
    "slack": "outbound channel; its installation routes ride `notifications`",
    "mattermost": "outbound channel",
    "telegram": "outbound channel; the legacy callback acknowledges and discards",
    "email": "outbound delivery policy, proven by the dispatch tests",
    "whatsapp": "shares messaging settings with sms (MULTI_GATED)",
    "member_accounts": "sign-in policy, proven by test_offstate_identity",
    "mobile": "device sessions; routes answer by credential, not tenant switch",
}


def test_every_api_route_is_in_the_snapshot():
    live = {(m, t) for t, methods in api_routes() for m in methods if m in {"GET", "POST"}}
    known = set(route_map()["base"])
    new = sorted(live - known)
    assert not new, f"routes missing from switch_matrix_snapshot.json (run regen_switch_matrix.py): {new[:10]}"


@pytest.mark.parametrize("state", ["base", "cold", "nofeat"])
def test_no_route_answers_5xx_in_any_switch_state(state):
    broken = sorted(f"{m} {t} -> {v}" for (m, t), v in route_map()[state].items()
                    if v[0] >= 500 and not (v[0] == 503 and t in TYPED_503))
    assert not broken, "\n" + "\n".join(broken)
    for (_m, t), v in route_map()[state].items():
        if t in TYPED_503 and v[0] == 503:
            assert v[1] in {None, "recovery_unavailable"}, (t, v)


def test_every_route_no_single_module_refuses_is_a_declared_either_or_route():
    undeclared = sorted(set(route_map()["either"]) - set(MULTI_GATED))
    assert not undeclared, f"routes refused with core only but by no single module: {undeclared}"


def test_every_optional_module_gates_a_route_or_is_declared_routeless():
    state = route_map()
    owned = {k for group in state["gates"].values() for k in group} | {k for g in MULTI_GATED.values() for k in g}
    missing = set(OPTIONAL) - owned - set(NO_ROUTE_MODULES)
    assert not missing, f"no route found for {sorted(missing)}: add a probe or declare it routeless with a reason"
    assert not (set(NO_ROUTE_MODULES) & owned), sorted(set(NO_ROUTE_MODULES) & owned)
    assert owned <= set(MODULE_KEYS), owned - set(MODULE_KEYS)


def test_every_capability_that_gates_a_route_is_a_live_registered_capability():
    keys = set(route_map()["features"].values())
    assert keys <= set(LIVE_FEATURES), keys - set(LIVE_FEATURES)
    assert len(keys) > 20


# --- the snapshot may only encode DECIDED behaviour ----------------------------------------------------------------
# Decisions 218/254: a switch that is off removes the surface (404, `module_disabled` for a shared guard, or the
# dedicated surface's own 404), and one that is on serves it normally. These rules are written here, from the registry,
# NOT read back from the crawl, so `regen_switch_matrix.py` cannot rewrite an expected refusal into a success: a
# regenerated snapshot that contradicts them fails this file and cannot be committed green.

REFUSAL_CODES = {None, "module_disabled", "shop_closed", "capability_disabled"}


def test_every_gated_route_is_refused_with_a_404_when_its_module_is_off():
    state, wrong = route_map(), []
    for route, group in state["gates"].items():
        status, code = state["cold"][route][:2]
        if status != 404 or code not in REFUSAL_CODES:
            wrong.append((route, status, code))
        if route in state["typed"] and code != "module_disabled":
            wrong.append((route, "typed gate must answer module_disabled", code))
    assert not wrong, f"snapshot contradicts the off rule (404 refusal): {wrong[:10]}"


def test_a_typed_gate_names_a_real_optional_module_never_a_core_one():
    from tests.modules.switch_matrix_helpers import CORE
    state = route_map()
    for route, group in state["gates"].items():
        assert group <= set(OPTIONAL), (route, sorted(group - set(OPTIONAL)))
        assert not (group & CORE), (route, "a core module cannot be switched off, so it cannot gate")


def test_every_gated_route_is_served_normally_when_everything_is_on():
    state, wrong = route_map(), []
    for route in list(state["gates"]) + list(MULTI_GATED):
        status, code = state["base"][route][:2]
        if status >= 500 or code in {"module_disabled", "feature_disabled"}:
            wrong.append((route, status, code))
    assert not wrong, f"snapshot contradicts the on rule (served): {wrong[:10]}"


def test_every_either_or_route_is_declared_by_hand_with_registered_modules():
    for route, group in MULTI_GATED.items():
        assert group <= set(OPTIONAL), (route, group)
        assert len(group) >= 2, route


def test_a_capability_refusal_is_a_404_feature_disabled_and_served_when_the_capability_is_on():
    state = route_map()
    for route, key in state["features"].items():
        assert state["nofeat"][route][:2] == (404, "feature_disabled"), (route, state["nofeat"][route])
        assert state["base"][route][1] != "feature_disabled", (route, key)
