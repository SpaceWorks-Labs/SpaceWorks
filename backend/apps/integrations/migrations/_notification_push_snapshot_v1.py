"""Frozen physical push snapshot, including when the optional app is tombstoned."""
import hashlib
import json

from django.core.serializers.json import DjangoJSONEncoder


def empty_snapshot():
    return {"count": 0, "max_id": 0, "sha256": hashlib.sha256().hexdigest(), "fields": []}


def snapshot(connection):
    table = "notifications_memberpushdelivery"
    if table not in connection.introspection.table_names():
        return None
    digest, count, last_id = hashlib.sha256(), 0, 0
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT * FROM {connection.ops.quote_name(table)} ORDER BY id")
        fields = [column[0] for column in cursor.description]
        while rows := cursor.fetchmany(500):
            for values in rows:
                row = dict(zip(fields, values))
                digest.update(json.dumps(row, cls=DjangoJSONEncoder, sort_keys=True).encode())
                count += 1
                last_id = row["id"]
    return {"count": count, "max_id": last_id, "sha256": digest.hexdigest(), "fields": fields}


def has_unmapped(connection, maximum):
    table = "notifications_memberpushdelivery"
    if table not in connection.introspection.table_names():
        return False
    quote = connection.ops.quote_name
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT EXISTS (SELECT 1 FROM {quote(table)} WHERE id <= %s AND id NOT IN "
            f"(SELECT legacy_id FROM {quote('integrations_notificationlegacymapping')} WHERE legacy_model = %s))",
            [maximum, "MemberPushDelivery"])
        return cursor.fetchone()[0]
