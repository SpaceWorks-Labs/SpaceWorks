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


def space_filter(view):
    from apps.makerspaces.models import Makerspace

    active = Makerspace.LifecycleState.ACTIVE.value.replace("'", "''")
    owned = (f"v.makerspace_id = ANY({FIXED_SCOPE}) AND EXISTS (SELECT 1 FROM {_table('makerspaces.Makerspace')} "
             f"spaceworks_ms WHERE spaceworks_ms.id = v.makerspace_id "
             f"AND spaceworks_ms.enabled_modules ? 'analytics' AND spaceworks_ms.archived_at IS NULL "
             f"AND spaceworks_ms.lifecycle_state = '{active}')")
    if view.include_unowned:
        return f"(v.makerspace_id IS NULL AND cardinality({FIXED_SCOPE}) > 0) OR ({owned})"
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
