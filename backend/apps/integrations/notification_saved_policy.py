"""Read retained opt-outs when the optional inbox app is not in Django's registry.

These physical-table reads can only constrain an independently authorized delivery.
They never import the removed app's models or manufacture a positive consent.
"""
import json
from types import SimpleNamespace

from django.db import connection


def saved_selection(space, user, category):
    table = "notifications_notificationpreference"
    if table not in connection.introspection.table_names():
        return None
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT channels, email_fallback FROM {connection.ops.quote_name(table)} "
            "WHERE makerspace_id = %s AND user_id = %s AND category = %s", [space.pk, user.pk, category])
        row = cursor.fetchone()
    if row is None:
        return None
    channels, fallback = row
    if isinstance(channels, str):
        try:
            channels = json.loads(channels)
        except ValueError:
            channels = None
    if not isinstance(channels, list) or any(not isinstance(value, str) for value in channels):
        return SimpleNamespace(channels=[], email_fallback=False)
    return SimpleNamespace(channels=channels, email_fallback=bool(fallback))


def opted_out(space, user_id, feature, channel):
    table = "notifications_membernotificationpreference"
    if table not in connection.introspection.table_names():
        return False
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT EXISTS (SELECT 1 FROM {connection.ops.quote_name(table)} "
            "WHERE makerspace_id = %s AND user_id = %s AND feature = %s AND channel = %s AND enabled = false)",
            [space.pk, user_id, feature, channel])
        return cursor.fetchone()[0]
