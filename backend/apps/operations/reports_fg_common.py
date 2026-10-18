"""Local calendar windows and action-scoped spaces for membership analytics."""

from datetime import timedelta

from dateutil.relativedelta import relativedelta

from apps.accounts import rbac
from apps.makerspaces.local_time import local_day_bounds, to_local
from apps.operations.membership_report_scope import report_queryset
from apps.operations.reports_common import report_spaces
from apps.operations.reports_finance_sources import finance_window


def scoped_spaces(makerspace_id, action, *, actor=None, modules=()):
    spaces = report_spaces(makerspace_id, *modules)
    for module in modules:
        spaces = spaces.filter(enabled_modules__contains=[module])
    if makerspace_id is not None:
        return report_queryset(spaces, makerspace_id, action, actor=actor, field="id")
    # The deployment scope is already restricted to eligible spaces.
    return spaces if actor is None else rbac.scope_by_action(actor, action, spaces, field="id")


def calendar_periods(space, first, last, grain):
    if grain not in ("day", "week", "month"):
        raise ValueError("Unsupported membership grain.")
    if first >= last:
        return
    day = to_local(space, first).date()
    if grain == "week":
        day -= timedelta(days=day.weekday())
    elif grain == "month":
        day = day.replace(day=1)
    while local_day_bounds(space, day)[0] < last:
        following = day + (relativedelta(months=1) if grain == "month" else timedelta(days=7 if grain == "week" else 1))
        yield day.isoformat(), max(first, local_day_bounds(space, day)[0]), min(last, local_day_bounds(space, following)[0])
        day = following


def membership_window(space, date_range, now, first):
    start, end = finance_window(space, date_range)
    return start or first, min(now, end) if end else now
