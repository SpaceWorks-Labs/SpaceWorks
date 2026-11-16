"""Exact-row permits for the immutable tables whose guards refuse the generic restore scope.

A one-space restore replaces the space's rows under ``app.allow_immutable_delete``. Two release-0.12
families do NOT honour that flag, on purpose: the retained venue decision
(``events_booking_decision_guard``) and the equipment proposal snapshots
(``inventory_equipment_snapshot_guard``) only release ONE row at a time, and only when transaction-local
settings name that row, its table and its owning makerspace. Without the same permit here the restore's
``DELETE`` raised "not authorized" and rolled the whole restore back for any space holding one of those rows.

The permit is read from the row itself (never from the caller), set for exactly one statement and cleared
straight after, exactly as ``makerspaces/booking_decision_purge.py`` and ``inventory/purge_equipment_proposals.py``
do for a whole-tenant purge.
"""

from django.db import connection

DECISION_TABLE = "events_eventbookingdecision"
EQUIPMENT_TABLES = frozenset({
    "inventory_equipmentproposalreceipt",
    "inventory_equipmentconsumableplan",
    "inventory_equipmentkitallocation",
    "inventory_equipmentkitversion",
    "inventory_equipmentconsumableusereceipt",
})
EXACT_ROW_TABLES = EQUIPMENT_TABLES | {DECISION_TABLE}
# A kit version is owned through its template; every other guarded table carries `makerspace_id`.
_OWNER_SQL = {
    "inventory_equipmentkitversion": (
        "SELECT t.makerspace_id FROM inventory_equipmentkitversion v "
        "JOIN inventory_equipmentkittemplate t ON t.id = v.template_id WHERE v.id = %s"
    ),
}


def guarded(model):
    return model._meta.db_table in EXACT_ROW_TABLES


def _owner(cursor, table, pk):
    cursor.execute(_OWNER_SQL.get(table, f'SELECT makerspace_id FROM "{table}" WHERE id = %s'), [pk])
    row = cursor.fetchone()
    return None if row is None else row[0]


def _permit(cursor, table, pk, owner, action):
    if table == DECISION_TABLE:
        cursor.execute(
            "SELECT set_config('app.booking_decision_purge_id', %s, true), "
            "set_config('app.booking_decision_purge_maker', %s, true), "
            "set_config('app.booking_decision_purge_action', %s, true)",
            [str(pk), str(owner), action],
        )
    else:
        cursor.execute(
            "SELECT set_config('app.equipment_purge_model', %s, true), "
            "set_config('app.equipment_purge_id', %s, true), "
            "set_config('app.equipment_purge_makerspace', %s, true)",
            [table, str(pk), str(owner)],
        )


def _clear(cursor, table):
    keys = (
        ("app.booking_decision_purge_id", "app.booking_decision_purge_maker", "app.booking_decision_purge_action")
        if table == DECISION_TABLE
        else ("app.equipment_purge_model", "app.equipment_purge_id", "app.equipment_purge_makerspace")
    )
    cursor.execute("SELECT " + ", ".join("set_config(%s, '', true)" for _ in keys), list(keys))


def delete_rows(model, pks):
    """Delete each row under its own exact permit; a row that is already gone is skipped."""
    table, column = model._meta.db_table, model._meta.pk.column
    with connection.cursor() as cursor:
        for pk in pks:
            db_pk = model._meta.pk.get_db_prep_value(pk, connection)
            owner = _owner(cursor, table, db_pk)
            if owner is None:
                continue
            _permit(cursor, table, db_pk, owner, "delete")
            cursor.execute(f'DELETE FROM "{table}" WHERE "{column}" = %s', [db_pk])
            _clear(cursor, table)


def null_reference(model, fk, pk):
    """Clear a retained decision's booking link under the guard's own ``detach`` permit.

    Returns True when handled. Every other guarded column stays immutable, so the caller falls through
    to its generic path (which the guard then refuses, and the restore reports as blocked).
    """
    table = model._meta.db_table
    if table != DECISION_TABLE or fk.name != "booking":
        return False
    db_pk = model._meta.pk.get_db_prep_value(pk, connection)
    with connection.cursor() as cursor:
        owner = _owner(cursor, table, db_pk)
        if owner is None:
            return True
        _permit(cursor, table, db_pk, owner, "detach")
        cursor.execute(
            f'UPDATE "{table}" SET "{fk.column}" = NULL WHERE "{model._meta.pk.column}" = %s AND "{fk.column}" IS NOT NULL',
            [db_pk],
        )
        _clear(cursor, table)
    return True
