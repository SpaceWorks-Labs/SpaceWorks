"""Informational context for the unification report; never part of ``plan_sha256``.

Per space: the superadmin's open PII windows and the platform security locks (owner
decisions #110c/#110e). Both are platform authority that the conversion leaves alone; the
report lists them so the operator sees the whole security picture before migrating.
Raw SQL against tables that exist before the unified-accounts schema.
"""

from collections import defaultdict


def _table_exists(connection, table):
    return table in connection.introspection.table_names()


def _rows(cursor, sql, params=()):
    cursor.execute(sql, params)
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def security_context(connection):
    """``{"open_pii_windows": [...], "security_locks": [...]}`` grouped by space."""
    windows, locks = defaultdict(int), defaultdict(list)
    with connection.cursor() as cursor:
        if _table_exists(connection, "accounts_platformpiiaccessgrant"):
            for row in _rows(cursor, """
                    SELECT makerspace_id, subject_id FROM accounts_platformpiiaccessgrant
                    WHERE closed_at IS NULL AND expires_at > now()"""):
                windows[row["makerspace_id"]] += 1
        if _table_exists(connection, "makerspaces_makerspacesecuritylock"):
            for row in _rows(cursor, """
                    SELECT makerspace_id, key FROM makerspaces_makerspacesecuritylock
                    ORDER BY makerspace_id, key"""):
                locks[row["makerspace_id"]].append(row["key"])
    return {
        # A window with no space is a per-person reveal; it is reported under ``null``.
        "open_pii_windows": [{"makerspace_id": space, "open": count}
                             for space, count in sorted(windows.items(), key=lambda item: item[0] or 0)],
        "security_locks": [{"makerspace_id": space, "keys": keys}
                           for space, keys in sorted(locks.items())],
    }
