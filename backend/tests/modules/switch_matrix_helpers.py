"""SWITCH-MATRIX helpers: enumerate the whole API from the URL conf and probe it under any switch state.

Nothing here lists a route or a module by hand. `api_routes()` walks the live resolver, `live_space()`
builds a tenant from a module/feature set, and `probe()` answers one route as a platform superadmin
inside a savepoint that is always rolled back, so a crawl never leaves a row behind and a route that
needs a body cannot half-write.
"""

import re
import uuid
from functools import lru_cache

from django.core.cache import cache
from django.db import transaction
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
_PARAM = re.compile(r"<(?:(?P<conv>\w+):)?(?P<name>\w+)>")
_UUID = str(uuid.UUID(int=1))


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


def root_client():
    user = User.objects.filter(username="switch-matrix-root").first() or User.objects.create_superuser(
        username="switch-matrix-root", email="switch-matrix-root@example.test", display_name="Matrix root",
        role=User.Role.SUPERADMIN, access_status=User.AccessStatus.ACTIVE,
    )
    client = APIClient(raise_request_exception=False)
    client.force_authenticate(user)
    return client


def probe(client, method, url):
    """One request, rolled back. Returns (status, code, key): `code` is module_disabled/feature_disabled/..., `key` names the switch."""
    cache.clear()
    try:
        with transaction.atomic():
            kwargs = {"format": "json"} if method in {"POST", "PUT", "PATCH"} else {}
            args = ({},) if kwargs else ()
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
    return response.status_code, code, key


def _creates_database_login(template):
    """Analytics/Grafana provisioning issues a real database role (CREATE ROLE blocks on the shared test cluster)."""
    return "/analytics/" in template and "/login" in template or "/grafana" in template


def crawl(client, space, *, methods=("GET", "POST"), only=None):
    """{(method, template): (status, code, key)} over every route (or only the templates in `only`)."""
    out = {}
    for template, route_methods in api_routes():
        if only is not None and template not in only:
            continue
        url = fill(template, space)
        for method in methods:
            if method in route_methods and not (method == "POST" and _creates_database_login(template)):
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
    ("GET", "/api/v1/admin/makerspace/<int:makerspace_id>/messaging-settings"): frozenset({"sms", "whatsapp"}),
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
        features={r: v[2] for r, v in nofeat.items() if v[1] == "feature_disabled" and v[2]},
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
    keys = OPTIONAL[shard::shards]
    return [(k, r) for k in keys for r in sorted(state["gates"]) if k in state["gates"][r] and r not in MULTI_GATED]


def feature_cases(shard, shards):
    state = route_map()
    keys = sorted(set(state["features"].values()))[shard::shards]
    return [(k, r) for k in keys for r in sorted(state["features"]) if state["features"][r] == k]


def case_id(case):
    key, (method, template) = case
    return f"{key}:{method}:{template}"[:150]
