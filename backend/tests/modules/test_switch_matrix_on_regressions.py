"""Mutation regressions for the live helpers; no HTTP expectation is learned from a mock."""
import copy
from types import SimpleNamespace

import pytest

from tests.modules import switch_matrix_helpers as helpers

METHOD_ROUTE = ("PATCH", "/api/v1/admin/makerspaces/<int:makerspace_id>/metabase/connection")
REFERENCE = ("GET", METHOD_ROUTE[1])
UNNAMED_ROUTE = ("GET", "/api/v1/admin/makerspace/<int:makerspace_id>/disputes")
WRONG_ON = (
    (401, "not_authenticated", None), (403, "permission_denied", None),
    (404, "not_found", None), (405, "method_not_allowed", None),
    (500, "server_error", None), (200, "unexpected_code", None),
)


def exercise_helper(monkeypatch, kind, responses):
    """Replace only transport/setup to inject one bad answer into the real assertions."""
    calls = []
    space = SimpleNamespace(pk=7, slug="reviewed", enabled_modules=["analytics"],
                            enabled_features=["stocktake.discipline"], save=lambda **kwargs: None)
    client = object()
    remaining = iter(responses)

    def probe(_client, method, url, **kwargs):
        assert _client is client
        calls.append((method, url, copy.deepcopy(kwargs),
                      tuple(space.enabled_modules), tuple(space.enabled_features)))
        return next(remaining)

    monkeypatch.setattr(helpers, "probe", probe)
    monkeypatch.setattr(helpers, "root_client", lambda **kwargs: client)
    monkeypatch.setattr(helpers, "live_space", lambda *args, **kwargs: space)
    monkeypatch.setattr(helpers, "dependents_closure", lambda key: set())
    monkeypatch.setattr(helpers, "FEATURES", {})
    monkeypatch.setattr(helpers, "route_map", lambda: {"cold": {REFERENCE: (404, "module_disabled", "analytics")}})

    def run():
        if kind == "unnamed":
            helpers.run_unnamed_case(UNNAMED_ROUTE, client, space)
        else:
            key = "analytics" if kind == "module" else "stocktake.discipline"
            helpers.run_variant_case((kind, key, METHOD_ROUTE, REFERENCE))

    return run, calls, space


def refusal(kind):
    if kind == "module":
        return (404, "module_disabled", "analytics")
    return (404, "feature_disabled", "stocktake.discipline" if kind == "feature" else None)


@pytest.mark.parametrize("kind", ["module", "feature", "unnamed"])
@pytest.mark.parametrize("phase", ["before", "restored"])
@pytest.mark.parametrize("wrong", WRONG_ON)
def test_live_helpers_reject_wrong_enabled_status_and_code(monkeypatch, kind, phase, wrong):
    responses = [(200, None, None), refusal(kind), (200, None, None)]
    responses[0 if phase == "before" else 2] = wrong
    if phase == "before":
        responses[2] = wrong  # A consistently broken on response must also fail.
    run, calls, _space = exercise_helper(monkeypatch, kind, responses)
    with pytest.raises(AssertionError) as caught:
        run()
    assert type(caught.value) is AssertionError
    selected_route = UNNAMED_ROUTE if kind == "unnamed" else METHOD_ROUTE
    assert str(caught.value).split("\n", 1)[0] == repr((" ".join(selected_route), wrong, (200, None, None)))
    assert len(calls) == (1 if phase == "before" else 3)


@pytest.mark.parametrize("kind", ["module", "feature", "unnamed"])
def test_live_helpers_restore_exact_response_on_the_same_tenant(monkeypatch, kind):
    run, calls, space = exercise_helper(monkeypatch, kind, [(200, None, None), refusal(kind), (200, None, None)])
    run()
    assert len(calls) == 3
    assert calls[0][:3] == calls[1][:3] == calls[2][:3]
    assert calls[0][3:] == calls[2][3:] == (("analytics",), ("stocktake.discipline",))
    assert calls[1][3:] == (((), ("stocktake.discipline",)) if kind == "module" else (("analytics",), ()))
    assert space.enabled_modules == ["analytics"]
    assert space.enabled_features == ["stocktake.discipline"]


@pytest.mark.parametrize("kind", ["module", "feature", "unnamed"])
def test_live_helpers_keep_exact_off_status_and_code(monkeypatch, kind):
    run, calls, _space = exercise_helper(monkeypatch, kind, [(200, None, None), (404, "not_found", None)])
    with pytest.raises(AssertionError):
        run()
    assert len(calls) == 2
