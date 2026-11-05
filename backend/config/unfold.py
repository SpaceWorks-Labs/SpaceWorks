import os

from django.templatetags.static import static
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

from apps.separability.tombstones import tombstoned_app_labels
from config.unfold_sidebar import build_navigation

SITE_NAME = os.environ.get("ADMIN_SITE_NAME", "Space Works")


def _is_active_superuser(request):
    user = getattr(request, "user", None)
    return bool(
        user
        and user.is_authenticated
        and user.is_active
        and user.is_superuser
        and getattr(user, "access_status", None)
        == getattr(getattr(user, "AccessStatus", None), "ACTIVE", "active")
    )


def _item(title, icon, route, app_label=None):
    """Build one sidebar entry, or None when its app has been tombstoned.

    Omitted rather than permission-hidden, which would not be enough: Unfold calls
    `str(link)` on every item to compute `active` *before* it consults the permission
    callback, so a `reverse_lazy` pointing at a route a tombstoned app no longer
    registers raises NoReverseMatch and 500s the entire console. `_prune_navigation`
    drops the Nones once the literal below is built.

    The tombstone list is read from the environment rather than from settings, because
    settings imports *this* module -- see `tombstones.tombstoned_app_labels`.

    `route` and `separable_app` are carried on the item so the drift-guard test can
    read them back. Unfold copies items through and only ever reads keys it knows, so
    the extra pair is inert.
    """
    if app_label is not None and app_label in tombstoned_app_labels():
        return None
    # Every admin model is superadmin-only (U-SEC), so a single permission gate
    # applies to the whole sidebar.
    return {
        "title": _(title),
        "icon": icon,
        "link": reverse_lazy(route),
        "permission": _is_active_superuser,
        "route": route,
        "separable_app": app_label,
    }


def _managed_active_superuser(request):
    return bool(os.environ.get("PLATFORM_DOMAIN_SUFFIX", "").strip()) and _is_active_superuser(request)


def _managed_item(title, icon, route, app_label=None):
    item = _item(title, icon, route, app_label=app_label)
    if item is None:
        # `_item` returns None for a tombstoned app; subscripting it here would turn a
        # supported tombstone into a boot crash.
        return None
    item["permission"] = _managed_active_superuser
    return item


def _plans_active_superuser(request):
    # The managed-hosting limiter's lists show only while it is on (#187A), exactly as their
    # admin's own has_module_permission says; read at request time, never at import.
    from apps.managed_hosting.availability import plans_enabled

    return plans_enabled() and _is_active_superuser(request)


def _plans_item(title, icon, route, app_label=None):
    item = _item(title, icon, route, app_label=app_label)
    if item is not None:
        item["permission"] = _plans_active_superuser
    return item


UNFOLD = {
    "SITE_TITLE": SITE_NAME,
    "SITE_HEADER": SITE_NAME,
    "SITE_ICON": {
        "light": lambda request: static("brand/symbol.svg"),
        "dark": lambda request: static("brand/symbol-reversed.svg"),
    },
    "SITE_LOGO": {
        "light": lambda request: static("brand/lockup-horizontal.svg"),
        "dark": lambda request: static("brand/lockup-horizontal-reversed.svg"),
    },
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    "THEME": "dark",
    "COLORS": {
        # Derived sRGB mixes: Teal toward Cream (50-400), Teal at 500/600,
        # then toward Deep Ink by 30/45/60/75 percent (700-950).
        "primary": {
            "50": "230 231 219",
            "100": "191 210 199",
            "200": "140 184 172",
            "300": "89 157 146",
            "400": "38 130 119",
            "500": "0 110 99",
            "600": "0 110 99",
            "700": "6 90 82",
            "800": "9 80 73",
            "900": "12 70 65",
            "950": "15 60 56",
        }
    },
    # #188: the /control/ home is a dashboard (key totals, what needs attention, quick links).
    "DASHBOARD_CALLBACK": "config.control_dashboard.dashboard_callback",
    "SIDEBAR": {
        "show_search": True,
        # Thirteen ordered sections built from the one catalogue (config.control_catalog);
        # every registered admin model appears in exactly one of them.
        "navigation": build_navigation(_item, _managed_item, _plans_item),
    },
}


def _prune_navigation(unfold):
    """Drop the entries `_item` returned None for, and any group left empty.

    A group whose every item belonged to tombstoned apps would otherwise render as a
    bare heading with a separator under it.
    """
    sidebar = unfold["SIDEBAR"]
    sidebar["navigation"] = [
        {**group, "items": kept}
        for group in sidebar["navigation"]
        if (kept := [item for item in group["items"] if item is not None])
    ]
    return unfold


_prune_navigation(UNFOLD)
