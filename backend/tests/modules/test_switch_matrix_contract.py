"""Pure snapshot validation, shared by the guard, generator and offline extractor.

The previous reviewed contracts are an input, never rediscovered from HTTP answers. A broken
gate cannot disappear from the next snapshot just because discovery no longer sees a refusal.
"""
import copy
import json
from pathlib import Path
import pytest
from apps.makerspaces.module_registry import MODULE_KEYS, core_module_keys
from apps.makerspaces.capability_definitions import FEATURES, RETIRED_FEATURES
from tests.modules.test_switch_matrix_on_responses import REVIEWED_ON

SNAPSHOT_PATH = Path(__file__).with_name("switch_matrix_snapshot.json")
OFF_CODES = {"module_disabled", "feature_disabled", "capability_disabled", "shop_closed", None}
SWITCH_CODES = OFF_CODES - {None}
UNAVAILABLE = {"GET /api/v1/live/", "GET /api/v1/health/readiness/", "POST /api/v1/auth/forgot-password"}


def reviewed_routes(state):
    return set().union(*(set(state[section]) for section in ("gates", "features", "either", "features_unnamed")))


def validate_snapshot(candidate, expected=None):
    """Raise before publication for unhealthy observations or loss of a reviewed expectation."""
    problems = []
    contracts = candidate.get("contracts")
    if not contracts or set(contracts) != {"gates", "features", "typed", "either", "features_unnamed", "off"}:
        raise ValueError("Snapshot contradicts switch contracts: missing reviewed contracts")
    for route, refusal in contracts["off"].items():
        if candidate["cold"].get(route) != refusal:
            problems.append((route, "reviewed off response changed", refusal, candidate["cold"].get(route)))
    routes = set(candidate["base"])
    optional = set(MODULE_KEYS) - set(core_module_keys())
    for route, group in candidate["gates"].items():
        if not group or not set(group) <= optional:
            problems.append((route, "gate must name optional registered modules", group))
    for route in candidate["typed"]:
        if candidate["cold"].get(route, [None, None, None])[2] not in optional:
            problems.append((route, "off refusal names no optional module"))
    for route, key in candidate["features"].items():
        if key not in FEATURES or key in RETIRED_FEATURES:
            problems.append((route, "gate must name a live registered capability", key))
    for state in ("base", "cold", "nofeat"):
        if set(candidate[state]) != routes:
            problems.append((state, "route sets disagree"))
        for route, value in candidate[state].items():
            if len(value) != 3 or value[0] >= 500 and not (value[0] == 503 and route in UNAVAILABLE):
                problems.append((state, route, value))
    for route in set(candidate["gates"]) | set(candidate["either"]):
        if route not in routes:
            problems.append((route, "missing route observation"))
            continue
        status, code, _ = candidate["cold"][route]
        if status != 404 or code not in OFF_CODES:
            problems.append((route, "off must refuse", candidate["cold"][route]))
        if candidate["base"][route][1] in SWITCH_CODES:
            problems.append((route, "on still refuses", candidate["base"][route]))
    for route in candidate["typed"]:
        if candidate["cold"].get(route, [])[:2] != [404, "module_disabled"]:
            problems.append((route, "typed module gate lost"))
    for route, key in candidate["features"].items():
        if candidate["nofeat"].get(route) != [404, "feature_disabled", key]:
            problems.append((route, "capability off must refuse and name its key"))
        if candidate["base"].get(route, [0, None])[1] in SWITCH_CODES:
            problems.append((route, "capability on must restore"))
    for route in candidate["features_unnamed"]:
        if candidate["nofeat"].get(route) != [404, "feature_disabled", None]:
            problems.append((route, "unnamed capability off must refuse"))
        if candidate["base"].get(route, [0, None])[1] in SWITCH_CODES:
            problems.append((route, "unnamed capability on must restore"))
    # Independent records prevent both a crawl and an edited embedded contract from
    # blessing an enabled refusal. New gates need explicit review before publication.
    for route in reviewed_routes(candidate) | reviewed_routes(contracts):
        on = REVIEWED_ON.get(route)
        if on is None or candidate["base"].get(route) != list(on):
            problems.append((route, "reviewed on response changed or unreviewed", on, candidate["base"].get(route)))
    if expected is not None:
        for route in reviewed_routes(expected):
            if candidate["base"].get(route) != expected["base"].get(route):
                problems.append((route, "previous reviewed on response changed", expected["base"].get(route)))
    for reviewed in (contracts, expected):
        if reviewed is None:
            continue
        for section in ("gates", "features"):
            for route, rule in reviewed[section].items():
                if candidate[section].get(route) != rule:
                    problems.append((section, route, "reviewed gate removed or rewritten", rule))
        for section in ("typed", "either", "features_unnamed"):
            if set(reviewed[section]) - set(candidate[section]):
                problems.append((section, "reviewed cases removed", sorted(set(reviewed[section]) - set(candidate[section]))))
    if problems:
        raise ValueError("Snapshot contradicts switch contracts: " + repr(problems[:20]))


def test_committed_snapshot_obeys_the_switch_contract():
    validate_snapshot(json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8")))


def test_generator_cannot_turn_a_reviewed_refusal_into_success_or_erase_it():
    expected = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    route = next(iter(expected["gates"]))
    for remove in (False, True):
        candidate = copy.deepcopy(expected)
        candidate["cold"][route] = [200, None, None]
        if remove:
            candidate["gates"].pop(route)
            for name in ("typed", "candidates", "either"):
                candidate[name] = [r for r in candidate[name] if r != route]
        with pytest.raises(ValueError, match="Snapshot contradicts switch contracts"):
            validate_snapshot(candidate, expected)


@pytest.mark.parametrize("section", ["gates", "features", "either", "features_unnamed"])
@pytest.mark.parametrize("wrong", [
    [401, "not_authenticated", None], [403, "permission_denied", None],
    [404, "not_found", None], [405, "method_not_allowed", None], [200, "unexpected_code", None],
])
@pytest.mark.parametrize("with_previous", [False, True])
def test_regeneration_rejects_changed_reviewed_on_status_or_code(section, wrong, with_previous):
    expected = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    route = next(route for route in sorted(expected[section]) if expected["base"][route] == [200, None, None])
    candidate = copy.deepcopy(expected)
    candidate["base"][route] = wrong
    with pytest.raises(ValueError, match="reviewed on response changed"):
        validate_snapshot(candidate, expected if with_previous else None)
    assert expected["base"][route] == [200, None, None]
    assert REVIEWED_ON[route] == (200, None, None)


def test_regeneration_cannot_rewrite_previous_expectations_alongside_the_candidate():
    expected = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    route = "GET /api/v1/admin/makerspace/<int:makerspace_id>/accountability"
    expected["base"][route] = [403, "permission_denied", None]
    with pytest.raises(ValueError, match="reviewed on response changed"):
        validate_snapshot(copy.deepcopy(expected), expected)
    assert REVIEWED_ON[route] == (200, None, None)


def test_regeneration_also_preserves_the_previous_reviewed_base():
    candidate = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    expected = copy.deepcopy(candidate)
    route = "GET /api/v1/admin/makerspace/<int:makerspace_id>/accountability"
    expected["base"][route] = [403, "permission_denied", None]
    with pytest.raises(ValueError, match="previous reviewed on response changed"):
        validate_snapshot(candidate, expected)
    assert candidate["base"][route] == [200, None, None]


def test_missing_object_baselines_remain_explicit_and_are_not_seeded_success():
    from tests.modules.test_switch_matrix_on_responses import MISSING_OBJECT_ON
    candidate = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    route = "GET /api/v1/admin/makerspace/<int:makerspace_id>/disputes/<int:dispute_id>"
    assert route in MISSING_OBJECT_ON
    assert REVIEWED_ON[route] == (404, "not_found", None)
    validate_snapshot(candidate, copy.deepcopy(candidate))


def test_regeneration_rejects_a_changed_error_code_with_the_same_error_status():
    expected = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    route = "POST /api/v1/admin/makerspaces/<int:makerspace_id>/metabase/login"
    assert expected["base"][route] == [400, "invalid", None]
    candidate = copy.deepcopy(expected)
    candidate["base"][route] = [400, "different_validation_code", None]
    with pytest.raises(ValueError, match="reviewed on response changed"):
        validate_snapshot(candidate, expected)
    assert expected["base"][route] == [400, "invalid", None]


def test_regeneration_rejects_a_new_gate_without_an_independent_reviewed_on_record():
    expected = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    candidate = copy.deepcopy(expected)
    route = "GET /api/v1/admin/makerspace/<int:makerspace_id>/unreviewed-switch-probe"
    candidate["base"][route] = candidate["nofeat"][route] = [200, None, None]
    candidate["cold"][route] = [404, "module_disabled", "analytics"]
    candidate["gates"][route] = ["analytics"]
    with pytest.raises(ValueError, match="reviewed on response changed or unreviewed"):
        validate_snapshot(candidate, expected)
    assert route not in REVIEWED_ON
