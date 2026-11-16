"""SWITCH-MATRIX helpers: enumerate the whole API from the URL conf and probe it under any switch state.

`api_routes()` walks the live resolver; reviewed negative-method probes are explicit. `live_space()`
builds a tenant from a module/feature set, and `probe()` answers one route as a platform superadmin
inside a savepoint that is always rolled back, so a crawl never leaves a row behind and a route that
needs a body cannot half-write.
"""

import re
import uuid
from contextlib import nullcontext
from functools import lru_cache
from types import SimpleNamespace
from unittest.mock import patch

from django.core.cache import cache
from django.db import connection, transaction
from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.makerspaces.capabilities import FEATURES
from apps.makerspaces.capability_definitions import RETIRED_FEATURES
from apps.makerspaces.models import Makerspace
from apps.makerspaces.module_registry import BY_KEY, MODULE_KEYS, core_module_keys

CORE = frozenset(core_module_keys())
OPTIONAL = tuple(sorted(MODULE_KEYS - CORE))
LIVE_FEATURES = tuple(sorted(set(FEATURES) - RETIRED_FEATURES))
# Not a product surface: the Django admin / control plane, API docs, health and static roots.
SKIP_PREFIXES = ("/control", "/docs", "/redoc", "/schema", "/static", "/media")
# Decision 507 also pins unsupported detail methods. Keep these negative probes
# during regeneration even though the live resolver correctly advertises DELETE only.
NEGATIVE_ROUTE_METHODS = {
    "/api/v1/admin/events/<int:pk>/certificates/signatories/<int:slot>/": frozenset({"GET", "POST", "PATCH", "PUT"}),
}
_PARAM = re.compile(r"<(?:(?P<conv>\w+):)?(?P<name>\w+)>")
_UUID = str(uuid.UUID(int=1))
# Successful response data in the reviewed triple, not an error code. Each probe rolls back.
INVITE_LINK_TEST_CODE = "ieVwjt8B6jpCb9j3l6mkqa_f"


class _Discard(Exception):
    pass


def _walk(patterns, prefix=""):
    for entry in patterns:
        if isinstance(entry, URLResolver):
            yield from _walk(entry.url_patterns, prefix + str(entry.pattern))
        elif isinstance(entry, URLPattern):
            yield prefix + str(entry.pattern), entry


def _methods(callback):
    cls = getattr(callback, "cls", None)
    actions = getattr(callback, "actions", None)
    if actions:
        return {m.upper() for m in actions}
    names = getattr(cls, "http_method_names", None) if cls else None
    if cls is None:
        return {"GET"}
    return {m.upper() for m in names or [] if hasattr(cls, m)} - {"OPTIONS", "HEAD"}


@lru_cache(maxsize=1)
def api_routes():
    """[(template, methods)] for every `<converter:name>` route under /api (regex routes are skipped)."""
    routes = []
    for template, entry in _walk(get_resolver().url_patterns):
        path = "/" + template.lstrip("^")
        if not path.startswith("/api") or path.startswith(SKIP_PREFIXES) or "(?" in path or "$" in path:
            continue
        routes.append((path, frozenset(_methods(entry.callback))))
    return sorted(set(routes))


def fill(template, space):
    """Substitute path parameters: the tenant's id/slug where the name says so, a fresh unused id otherwise."""
    def value(match):
        name, conv = match["name"], match["conv"] or "str"
        if name == "kind" and "/calendar-feeds/" in template:
            return "shifts"
        if "makerspace" in name and conv == "int":
            return str(space.pk)
        if name in {"slug", "makerspace_slug", "space_slug"} or name.endswith("_slug") and "makerspace" in name:
            return space.slug
        if conv == "int":
            return "987654"
        if conv == "uuid":
            return _UUID
        return "x"
    return _PARAM.sub(value, template)


def live_space(slug, modules, features=None):
    """A tenant with exactly `modules` (+ core) and `features` (default: every live switch)."""
    return Makerspace.objects.create(
        name=slug, slug=slug, public_inventory_enabled=True,
        enabled_modules=sorted(set(modules) | CORE),
        enabled_features=sorted(LIVE_FEATURES if features is None else features),
    )


def root_client(*, verified=False):
    user = User.objects.filter(username="switch-matrix-root").first() or User.objects.create_superuser(
        username="switch-matrix-root", email="switch-matrix-root@example.test", display_name="Matrix root",
        role=User.Role.SUPERADMIN, access_status=User.AccessStatus.ACTIVE,
    )
    if verified:
        from tests.return_helpers import authenticated_client
        return authenticated_client(user)
    client = APIClient(raise_request_exception=False)
    client.force_authenticate(user)
    return client


def probe(client, method, url, *, body=None):
    """One rolled-back request: (status, top-level code, switch key), including successful code data."""
    cache.clear()
    writes = []
    # Patch only this service's entropy reference; keep authorization, serializers,
    # persistence and audits real, and leave every other consumer of secrets alone.
    entropy = patch(
        "apps.makerspaces.membership_invite_links.secrets",
        SimpleNamespace(token_urlsafe=lambda _size: INVITE_LINK_TEST_CODE),
    ) if method == "POST" and re.fullmatch(
        r"/api/v1/admin/makerspaces/\d+/membership-invite-links/?", url,
    ) else nullcontext()

    def record_write(execute, sql, params, many, context):
        if re.search(r"\b(CREATE|ALTER|DROP)\s+ROLE\b|\b(?:ensure_login|drop_login)\s*\(", sql, re.I):
            raise AssertionError("The switch probe must never provision or revoke database roles")
        if re.match(r"\s*(INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|TRUNCATE)\b", sql, re.I):
            writes.append(sql.split(None, 1)[0])
        return execute(sql, params, many, context)

    try:
        with entropy, transaction.atomic(), connection.execute_wrapper(record_write):
            kwargs = {"format": "json"} if method in {"POST", "PUT", "PATCH"} or body is not None else {}
            args = ({} if body is None else body,) if kwargs else ()
            response = getattr(client, method.lower())(url, *args, **kwargs)
            raise _Discard(response)
    except _Discard as done:
        response = done.args[0]
    data = getattr(response, "data", None)
    code = key = None
    if isinstance(data, dict):
        code = data.get("code")
        key = data.get("module") or data.get("feature")
        code = None if code is None else str(code)
        key = None if key is None else str(key)
    if response.status_code == 404 and code in {"module_disabled", "feature_disabled", "capability_disabled"}:
        assert writes == [], (method, url, "refused request attempted database writes", writes)
    return response.status_code, code, key


def crawl(client, space, *, methods=("GET", "POST", "PUT", "PATCH", "DELETE"), only=None):
    """{(method, template): (status, code, key)} over every route (or only the templates in `only`)."""
    out = {}
    for template, route_methods in api_routes():
        if only is not None and template not in only:
            continue
        url = fill(template, space)
        for method in methods:
            if method in route_methods or method in NEGATIVE_ROUTE_METHODS.get(template, ()):
                out[(method, template)] = probe(client, method, url)
    return out


# --- the covering array --------------------------------------------------------------------------


def closure_on(keys):
    """`keys` plus everything they require, transitively (a valid 'on' set)."""
    from apps.makerspaces.module_registry import with_dependencies
    return set(with_dependencies(keys)) - CORE


def feasible_pairs(keys=OPTIONAL):
    """Every (a, va, b, vb) some valid tenant can have, and the impossible ones with the reason.

    A pair is impossible when one side is ON and the other OFF but the OFF key is required by the ON one
    (`requires_modules`, transitively): the registry refuses that tenant.
    """
    feasible, impossible = set(), {}
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            for va in (0, 1):
                for vb in (0, 1):
                    if va and not vb and b in closure_on({a}):
                        impossible[(a, va, b, vb)] = f"{a} requires {b}"
                    elif vb and not va and a in closure_on({b}):
                        impossible[(a, va, b, vb)] = f"{b} requires {a}"
                    else:
                        feasible.add((a, va, b, vb))
    return feasible, impossible


def pairwise_rows(keys=OPTIONAL, seed=20261113, candidates=40):
    """Deterministic greedy all-pairs covering array; every row is a valid module set. Returns [frozenset(on)]."""
    import random
    rng = random.Random(seed)
    feasible, _ = feasible_pairs(keys)
    uncovered, rows = set(feasible), []

    def covered(on):
        return {(a, int(a in on), b, int(b in on)) for i, a in enumerate(keys) for b in keys[i + 1:]} & uncovered

    while uncovered:
        target = rng.choice(sorted(uncovered))
        best, best_gain = None, -1
        for _ in range(candidates):
            on = {k for k in keys if rng.random() < 0.5}
            for k, v in ((target[0], target[1]), (target[2], target[3])):
                on = on | {k} if v else on - {k}
            on = closure_on(on) if True else on
            # Dropping a key may strand a dependent: repair by dropping dependents of any OFF key.
            for k in [k for k in keys if k not in on]:
                on -= {d for d in keys if k in closure_on({d}) and d != k}
            if {k for k in closure_on(on)} != on:
                continue
            gain = len(covered(on))
            if gain > best_gain:
                best, best_gain = frozenset(on), gain
        if best is None or best_gain <= 0:
            uncovered.discard(target)
            continue
        rows.append(best)
        uncovered -= covered(best)
    return rows


# --- the route -> switch map, derived once per process -------------------------------------------

_MAP = {}

# A route declared by TWO modules (either one keeps it served), so one module off alone cannot refuse it.
# Each is proven in `test_switch_matrix_routes`: refused only when every module of its group is off.
MULTI_GATED = {
    ("GET", "/api/v1/admin/makerspaces/<int:makerspace_id>/guest-pass-policy"): frozenset({"membership", "presence"}),
    ("GET", "/api/v1/admin/makerspaces/<int:makerspace_id>/wallet-credentials"): frozenset({"membership", "events"}),
    ("PATCH", "/api/v1/admin/makerspaces/<int:makerspace_id>/wallet-credentials"): frozenset({"membership", "events"}),
    ("GET", "/api/v1/admin/makerspace/<int:makerspace_id>/messaging-settings"): frozenset({"sms", "whatsapp"}),
}
MULTI_FEATURE_GATED = {
    (method, "/api/v1/admin/makerspaces/<int:makerspace_id>/wallet-credentials"):
        frozenset({"membership.wallet_passes", "events.wallet_passes"}) for method in ("GET", "PATCH")
}
# Not an API surface of a tenant: process health and the recovery probe answer a deliberate typed 503.
TYPED_503 = {"/api/v1/live/", "/api/v1/health/readiness/", "/api/v1/auth/forgot-password"}


def compute_route_map():
    """(SLOW, ~10 min: only `regen_switch_matrix.py` calls it) The route -> switch map from crawls of the live URL conf.

    `gates`: {route: frozenset(modules)}. A module is in a route's gate set when turning ONLY that module (and what
        requires it) off refuses the route while every other module is on: exactly `module_disabled` 404 for a
        typed gate, or the plain 404 a dedicated surface gives (only for routes that are served in the all-on
        crawl, so a 404 for a missing object is never mistaken for a gate). A route needing two modules has both
        in its set; a route either of two keeps served is declared in MULTI_GATED and checked separately.
    `typed`: the routes whose gate is the typed `module_disabled` refusal (in the core-only crawl).
    `features`: routes refusing `feature_disabled` naming a key, with every module on and no feature on.
    """
    client = root_client()
    base = crawl(client, live_space("sx-base", MODULE_KEYS))
    cold = crawl(client, live_space("sx-cold", set()))
    nofeat = crawl(client, live_space("sx-nofeat", MODULE_KEYS, features=[]))
    typed = {r for r, v in cold.items() if v[:2] == (404, "module_disabled")}
    # Dedicated surfaces refuse with their own 404 (untyped, or `shop_closed`); only routes SERVED in the all-on
    # crawl count, so a 404 for a missing object is never mistaken for a gate.
    candidates = typed | {
        r for r, v in cold.items()
        if v[0] == 404 and v[1] in (None, "shop_closed", "capability_disabled") and r in base
        and base[r][0] not in (404, 401) and base[r][0] < 500
    }
    templates = {t for _m, t in candidates}
    gates = {}
    for key in OPTIONAL:
        off = {key} | dependents_closure(key)
        space = live_space(f"sx-lo-{key.replace('_', '-')}", set(MODULE_KEYS) - off)
        for r, v in crawl(client, space, only=templates).items():
            if r in candidates and v[:2] == cold[r][:2]:
                gates.setdefault(r, set()).add(key)
    return dict(
        base=base, cold=cold, nofeat=nofeat, typed=typed, candidates=candidates,
        gates={r: frozenset(g) for r, g in gates.items()},
        either=sorted(r for r in candidates if r not in gates),
        features={r: v[2] for r, v in nofeat.items()
                  if v[1] == "feature_disabled" and v[2] and r not in MULTI_FEATURE_GATED},
        features_unnamed=sorted(r for r, v in nofeat.items() if v[1] == "feature_disabled" and not v[2]),
    )


def dependents_closure(key):
    """Every optional module that (transitively) requires `key`."""
    return {m for m in OPTIONAL if m != key and key in closure_on({m})}


# --- the committed snapshot --------------------------------------------------------------------------------------

import json  # noqa: E402
import pathlib  # noqa: E402

SNAPSHOT = pathlib.Path(__file__).with_name("switch_matrix_snapshot.json")
_KEY = " "


def _enc(route):
    return f"{route[0]}{_KEY}{route[1]}"


def _dec(text):
    method, template = text.split(_KEY, 1)
    return method, template


def encode_map(state):
    out = {}
    for name in ("base", "cold", "nofeat"):
        out[name] = {_enc(r): list(v) for r, v in state[name].items()}
    for name in ("typed", "candidates", "either", "features_unnamed"):
        out[name] = sorted(_enc(r) for r in state[name])
    out["gates"] = {_enc(r): sorted(g) for r, g in state["gates"].items()}
    out["features"] = {_enc(r): k for r, k in state["features"].items()}
    return out


def route_map():
    """The route -> switch map. Loaded from the committed snapshot (the crawl takes ~10 min); the snapshot is kept
    honest by `test_switch_matrix_snapshot_guard` (every API route is in it) and rebuilt by
    `regen_switch_matrix.py` (instructions in that file)."""
    if not _MAP:
        raw = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        state = {}
        for name in ("base", "cold", "nofeat"):
            state[name] = {_dec(k): tuple(v) for k, v in raw[name].items()}
        for name in ("typed", "candidates"):
            state[name] = {_dec(k) for k in raw[name]}
        for name in ("either", "features_unnamed"):
            state[name] = sorted(_dec(k) for k in raw[name])
        state["gates"] = {_dec(k): frozenset(v) for k, v in raw["gates"].items()}
        state["features"] = {_dec(k): v for k, v in raw["features"].items()}
        _MAP.update(state)
    return _MAP


# --- one fast case per (switch, route) -----------------------------------------------------------------------------


def module_cases(shard, shards):
    """[(module, route)] this shard owns: every route a module gates (either-or routes are tested separately)."""
    state = route_map()
    cases = [(k, r) for k in OPTIONAL for r in sorted(state["gates"])
             if k in state["gates"][r] and r not in MULTI_GATED]
    return cases[shard::shards]


def feature_cases(shard, shards):
    state = route_map()
    cases = sorted((key, route) for route, key in state["features"].items() if route not in MULTI_FEATURE_GATED)
    return cases[shard::shards]


def case_id(case):
    key, (method, template) = case
    return f"{key}:{method}:{template}"[:150]


@lru_cache(maxsize=1)
def variant_cases():
    """Mutating verbs on a known gated surface inherit that surface's reviewed off rule.

    Discovery reads only the resolver and the reviewed contract, never today's HTTP answer.
    Either-or surfaces have their own exhaustive switch tests rather than a single-key rule.
    """
    state, cases = route_map(), {}
    shared = {template for _, template in (*MULTI_GATED, *MULTI_FEATURE_GATED)}
    methods = {}
    for template, names in api_routes():
        methods.setdefault(template, set()).update(names)
    for section, kind in (("gates", "module"), ("features", "feature")):
        for reference, group in state[section].items():
            template = reference[1]
            if template in shared:
                continue
            for method in methods.get(template, set()) - {"GET", "POST"}:
                route = (method, template)
                if route in state["base"]:
                    continue
                for key in ([group] if kind == "feature" else group):
                    identity = (kind, key, route)
                    previous = cases.get(identity)
                    if previous and kind == "module":
                        assert state["cold"][previous][:2] == state["cold"][reference][:2], (
                            "declare the method-specific off policy", previous, reference)
                    cases.setdefault(identity, reference)
    return tuple(sorted((*identity, reference) for identity, reference in cases.items()))


def run_variant_case(case):
    from tests.modules.test_switch_matrix_method_contracts import assert_method_on, method_body
    kind, key, route, reference = case
    client = root_client(verified=True)
    space = live_space("sx-method", MODULE_KEYS)
    url = fill(route[1], space)
    body = method_body(route)
    assert_method_on(route, probe(client, route[0], url, body=body))
    field = "enabled_modules" if kind == "module" else "enabled_features"
    original = getattr(space, field)
    off = {key} | dependents_closure(key) if kind == "module" else {key}
    if kind == "feature":
        while True:
            requiring = {name for name, definition in FEATURES.items() if set(definition.requires_features) & off}
            if requiring <= off:
                break
            off |= requiring
    setattr(space, field, sorted(set(original) - off))
    space.save(update_fields=[field])
    refused = probe(client, route[0], url, body=body)
    expected = (404, "feature_disabled") if kind == "feature" else tuple(route_map()["cold"][reference][:2])
    assert refused[:2] == expected, (case, refused, expected)
    if refused[1] in {"module_disabled", "feature_disabled"}:
        assert refused[2] in off, (case, refused)
    setattr(space, field, original)
    space.save(update_fields=[field])
    assert_method_on(route, probe(client, route[0], url, body=body))


def run_unnamed_case(route, client, space):
    """Pin all three responses on one tenant; probe still detects off-state writes."""
    from tests.modules.test_switch_matrix_on_responses import assert_reviewed_on
    url = fill(route[1], space)
    assert_reviewed_on(route, probe(client, route[0], url))
    original = space.enabled_features
    space.enabled_features = []
    space.save(update_fields=["enabled_features"])
    assert probe(client, route[0], url) == (404, "feature_disabled", None), route
    space.enabled_features = original
    space.save(update_fields=["enabled_features"])
    assert_reviewed_on(route, probe(client, route[0], url))


def assert_no_tenant_oracle(route, space, key):
    """A manager elsewhere gets the same typed 404 in either switch state (#481/#494)."""
    if not route[1].startswith(("/api/v1/admin/makerspace/", "/api/v1/admin/makerspaces/")):
        return
    from tests.fixed_roles.helpers import staff_account
    from tests.return_helpers import authenticated_client
    other = live_space("sx-no-standing", MODULE_KEYS)
    client = authenticated_client(staff_account(other, "sx-other-manager", "space_manager"))
    original = space.enabled_modules
    for modules in (original, sorted(set(original) - {key} - dependents_closure(key))):
        space.enabled_modules = modules
        space.save(update_fields=["enabled_modules"])
        result = probe(client, route[0], fill(route[1], space))
        assert result[:2] == (404, "not_found"), (key, route, result)
    space.enabled_modules = original
    space.save(update_fields=["enabled_modules"])
