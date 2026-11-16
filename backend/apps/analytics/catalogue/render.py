"""Render one curated view as SQL for the space schema or the platform schema.

The space wrapper is the view's own scoping (see ``types``): the login's fixed space from
``spaceworks_rls_fixed_scope(current_user)`` (a non-definer view evaluates ``current_user``
as the login that queries it), the space must have the analytics switch on and be servable.
A login with no fixed space sees nothing, including the unowned rows of a lookup view.
"""

from django.apps import apps

from .types import q

SPACE = "space"
PLATFORM = "platform"
FIXED_SCOPE = "public.spaceworks_rls_fixed_scope(current_user::text)"


def _table(label):
    return 'public."' + apps.get_model(label)._meta.db_table + '"'


def _pii(column, makerspace, audience):
    if audience == PLATFORM:
        return f"NULL::{column.pii_type}"
    allowed = (f"EXISTS (SELECT 1 FROM {_table('analytics.AnalyticsConnection')} spaceworks_pii "
               f"WHERE spaceworks_pii.makerspace_id = {makerspace} AND spaceworks_pii.show_member_details)")
    return f"CASE WHEN {allowed} THEN ({column.expr})::{column.pii_type} END"


def inner_sql(view, audience):
    columns = [f"{view.makerspace} AS makerspace_id"]
    for column in view.columns:
        expr = _pii(column, view.makerspace, audience) if column.pii else column.expr
        columns.append(f"{expr} AS {q(column.name)}")
    return f"SELECT {', '.join(columns)} {view.resolved_source()}"


# Decision 218 (full on/off audit, 0.12.0): a view of an optional domain returns no rows while
# that module or capability is off for the space; the rows are kept. `View.requires` overrides.
DOMAIN_SWITCHES = {"machines": ("machines",), "bookings": ("bookings",), "events": ("events",),
                   "tickets": ("events",), "shop": ("shop",), "donations": ("finance.donations",)}


def switch_keys(view):
    """`(modules, features)` the space must have on: the keys plus each feature's parents."""
    from apps.makerspaces.capabilities import FEATURES

    pending = list(DOMAIN_SWITCHES.get(view.domain, ()) if view.requires is None else view.requires)
    modules, features = set(), set()
    while pending:
        key = pending.pop()
        if "." not in key:
            modules.add(key)
        elif key not in features:
            features.add(key)
            definition = FEATURES[key]
            modules.update(m for m in (definition.parent_module, *definition.requires_modules) if m)
            pending.extend(definition.requires_features)
    return sorted(modules), sorted(features)


def _switch_sql(view):
    modules, features = switch_keys(view)
    return "".join([f"AND spaceworks_ms.enabled_modules ? '{key}' " for key in modules]
                   + [f"AND spaceworks_ms.enabled_features ? '{key}' " for key in features])


def space_filter(view):
    from apps.makerspaces.models import Makerspace

    active = Makerspace.LifecycleState.ACTIVE.value.replace("'", "''")

    def gate(space_match):
        return (f"EXISTS (SELECT 1 FROM {_table('makerspaces.Makerspace')} spaceworks_ms WHERE {space_match} "
                f"AND spaceworks_ms.enabled_modules ? 'analytics' {_switch_sql(view)}"
                f"AND spaceworks_ms.archived_at IS NULL AND spaceworks_ms.lifecycle_state = '{active}')")

    owned = f"v.makerspace_id = ANY({FIXED_SCOPE}) AND {gate('spaceworks_ms.id = v.makerspace_id')}"
    if view.include_unowned:
        # Unowned rows (built-in machine types) follow the login's OWN space's switches too, so a
        # space with analytics (or the area) off sees nothing at all (decision 263 isolation pass).
        return f"(v.makerspace_id IS NULL AND {gate(f'spaceworks_ms.id = ANY({FIXED_SCOPE})')}) OR ({owned})"
    return owned


def render(view, audience):
    inner = inner_sql(view, audience)
    if audience == PLATFORM:
        return inner
    return f"SELECT v.* FROM ({inner}) v WHERE {space_filter(view)}"


def catalog_sql(views, version):
    """The ``views_catalog`` view: name, domain, since and the catalogue version."""
    rows = ", ".join(
        f"('{view.name}', '{view.domain}', {int(view.since)}, {int(version)})" for view in views
    ) or "(NULL, NULL, NULL, NULL)"
    return (f"SELECT name::text, domain::text, since::integer, views_version::integer "
            f"FROM (VALUES {rows}) catalog(name, domain, since, views_version)")
