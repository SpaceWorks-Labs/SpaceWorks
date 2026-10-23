"""Persist circular recovery progress so one unavailable page cannot starve later work."""
from django.db import transaction


def take_ids(namespace, queryset, *, limit=100):
    from .submissions.models_assets import EventProgrammeSweepCursor
    if type(limit) is not int or not 1 <= limit <= 500:
        raise ValueError("Use a bounded recovery batch.")
    with transaction.atomic():
        cursor, _ = EventProgrammeSweepCursor.objects.get_or_create(namespace=namespace)
        cursor = EventProgrammeSweepCursor.objects.select_for_update().get(pk=cursor.pk)
        rows = queryset.filter(pk__gt=cursor.last_id).order_by("pk")
        ids = list(rows.values_list("pk", flat=True)[:limit])
        if not ids and cursor.last_id:
            ids = list(queryset.order_by("pk").values_list("pk", flat=True)[:limit])
        cursor.last_id = ids[-1] if ids else 0
        cursor.save(update_fields=["last_id"])
        return ids
