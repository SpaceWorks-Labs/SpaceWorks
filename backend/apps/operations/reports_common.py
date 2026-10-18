from django.db.models import QuerySet
from django.db.models.functions import TruncDay, TruncMonth, TruncWeek

from apps.makerspaces.models import Makerspace
from apps.operations.report_scope import scoped_ids


def report_spaces(makerspace_id, *required_modules) -> QuerySet:
    return Makerspace.objects.filter(
        id__in=scoped_ids(makerspace_id, *required_modules)
    ).order_by("id")


def apply_range(queryset, field, date_range):
    if not date_range:
        return queryset
    start, end = date_range
    if start is not None:
        queryset = queryset.filter(**{f"{field}__gte": start})
    if end is not None:
        queryset = queryset.filter(**{f"{field}__lt": end})
    return queryset


def period_expression(field, grain, *, makerspace=None, tzinfo=None):
    """SQL calendar bucket; ISO weeks start Monday in the selected local zone.

    Subject/membership builders pass their already-resolved makerspace. Deployment
    builders must group/query each tenant separately when local dates are required.
    Other callers retain Django's current timezone, as before.
    """
    if makerspace is not None:
        from zoneinfo import ZoneInfo
        if tzinfo is not None:
            raise ValueError("Pass makerspace or tzinfo, not both.")
        tzinfo = ZoneInfo(makerspace.timezone)
    trunc = {"day": TruncDay, "week": TruncWeek, "month": TruncMonth}.get(grain)
    if trunc is None:
        raise ValueError("Unsupported report grain.")
    return trunc(field, tzinfo=tzinfo)


def limited(records, limit):
    return records if limit is None else records[:limit]
