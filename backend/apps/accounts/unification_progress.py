"""Merge progress for ``account_unification_report`` once the database is unified (U-C).

Informational only and never part of ``plan_sha256``: the pre-migration plan digest stays
exactly what the operator acknowledged. Before the unified-accounts schema exists this
returns ``None`` (the merge tables are not there yet). Raw SQL, like the plan.
"""


def _scalar(cursor, sql, params=()):
    cursor.execute(sql, params)
    return cursor.fetchone()[0] or 0


def merge_progress(connection):
    tables = connection.introspection.table_names()
    if "accounts_accountmergerecord" not in tables:
        return None
    with connection.cursor() as cursor:
        converted = _scalar(cursor, "SELECT count(*) FROM accounts_accountmergerecord WHERE decision = 'converted'")
        merged = _scalar(cursor, """SELECT count(*) FROM accounts_accountmergerecord
                                    WHERE decision = 'merged' AND state = 'completed'""")
        # A converted account still a person (not merged away) whose address is held.
        held = _scalar(cursor, """
            SELECT count(*) FROM accounts_accountmergerecord r JOIN accounts_user u ON u.id = r.source_id
            WHERE r.decision = 'converted' AND u.merged_into_id IS NULL AND r.held_fields ? 'email'""")
        unmerged = _scalar(cursor, """
            SELECT count(*) FROM accounts_accountmergerecord r JOIN accounts_user u ON u.id = r.source_id
            WHERE r.decision = 'converted' AND u.merged_into_id IS NULL""")
        passkeys = "accounts_webauthncredential" in tables
        unenrolled = _scalar(cursor, f"""
            SELECT count(DISTINCT u.id) FROM accounts_user u
            JOIN makerspaces_makerspacemembership m
              ON m.user_id = u.id AND m.track = 'staff' AND m.status = 'active'
            WHERE u.account_kind = 'member' AND u.is_active
              AND NOT EXISTS (SELECT 1 FROM accounts_usermfa f WHERE f.user_id = u.id AND f.enabled_at IS NOT NULL)
              {"AND NOT EXISTS (SELECT 1 FROM accounts_webauthncredential w WHERE w.user_id = u.id)"
               if passkeys else ""}""")
    return {"converted": converted, "merged": merged, "converted_not_merged": unmerged,
            "held_emails": held, "unenrolled_staff": unenrolled}
