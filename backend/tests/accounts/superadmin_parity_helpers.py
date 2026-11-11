"""Census of the staff routes a Space Manager uses, for the #115 parity guard."""

import re

from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.test import APIClient

from apps.accounts.delegated_routes import route_class
from apps.accounts.platform_tenant_surface import TENANT_CLASSES
from apps.accounts.tokens import SpaceWorksRefreshToken

PLATFORM_ORIGIN = "http://localhost:5000"
SPACE_KWARGS = {"makerspace_id", "makerspace_pk"}
_CONVERTER = re.compile(r"<(?:(?P<conv>[a-z]+):)?(?P<name>\w+)>")
_FILLERS = {"int": "999999", "slug": "missing", "str": "missing", "uuid": "00000000-0000-4000-8000-000000000000",
            "path": "missing"}
_KNOWN = {"report_key": "summary"}


def _walk(patterns, prefix=""):
    for pattern in patterns:
        route = getattr(pattern.pattern, "_route", None)
        if route is None:  # re_path: no reversible route string
            continue
        if isinstance(pattern, URLResolver):
            yield from _walk(pattern.url_patterns, prefix + route)
        elif isinstance(pattern, URLPattern) and pattern.name:
            yield prefix + route, pattern.name, pattern.default_args


def census():
    """Every named tenant staff route (membership-only or delegable) outside /api/v1/auth/."""
    rows, seen = [], set()
    for route, name, defaults in _walk(get_resolver().url_patterns):
        if not route.startswith("api/v1/") or route.startswith("api/v1/auth/"):
            continue
        if route_class(name) not in TENANT_CLASSES or (route, name) in seen:
            continue
        seen.add((route, name))
        rows.append((route, name))
    return rows


# P38 (#115c): the shop runs on its own module and switches, so the parity world turns them on;
# with the shop off every shop route is a 404 for both sides and the census would compare nothing.
SHOP_MODULES = frozenset({"shop"})
SHOP_FEATURES = frozenset({"charges.enabled", "charges.shop", "shop.online", "shop.returns", "shop.cash_up",
                           "shop.receipts"})
SHOP_LIST_ROUTES = ("admin-shop-settings", "admin-shop-products", "admin-shop-movements", "admin-shop-orders",
                    "admin-shop-report", "admin-shop-cash-sessions")


def open_shop(space):
    """Turn the shop module and its switches on in one parity space."""
    space.enabled_modules = sorted(set(space.enabled_modules or []) | SHOP_MODULES)
    space.enabled_features = sorted(set(space.enabled_features or []) | SHOP_FEATURES)
    space.save(update_fields=["enabled_modules", "enabled_features"])
    return space


def shop_census():
    """The census rows that belong to the shop's staff surface."""
    return [(route, name) for route, name in census() if name.startswith("admin-shop-")]


def space_kwargs(name):
    """The kwargs that name the makerspace on this route (origin-scope registry)."""
    from apps.makerspaces.origin_scope_routes_catalog import MAKERSPACE_KWARG_ROUTES
    extra = {"pk"} if name.startswith("makerspace-public-page-") or name == "admin-makerspace" else set()
    registered = MAKERSPACE_KWARG_ROUTES.get(name)
    return SPACE_KWARGS | extra | ({registered} if isinstance(registered, str) else set())


def path_for(route, space_id, name=""):
    kwargs = space_kwargs(name)

    def fill(match):
        if match["name"] in kwargs:
            return str(space_id)
        return _KNOWN.get(match["name"]) or _FILLERS.get(match["conv"] or "str", "missing")
    # Query-scoped listings (events, rosters, ...) narrow by this hint; other routes ignore it.
    return "/" + _CONVERTER.sub(fill, route) + f"?makerspace={space_id}"


def only_space_kwargs(route, name=""):
    names = {match["name"] for match in _CONVERTER.finditer(route)}
    return bool(names) and names <= space_kwargs(name) | set(_KNOWN)


def bearer(user, *, origin=None):
    token = SpaceWorksRefreshToken.for_user(user)
    client = APIClient(raise_request_exception=False)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}",
                       **({"HTTP_ORIGIN": origin} if origin else {}))
    return client
