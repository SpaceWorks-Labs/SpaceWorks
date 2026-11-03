"""Idempotent post-migrate application of the generated policies (``manage.py rls_sync``).

Runs as the migrating role after every ``migrate`` (and test-database flush), so a table
a later lane adds is policed by the next migrate with nothing but its classification.
Unchanged tables cost nothing: one catalog read compares each policy's fingerprint
comment. A table the role cannot alter is reported, never fatal: migrate must not fail.
"""

import logging
from dataclasses import dataclass, field

from django.db import connections, transaction

from .policies import FIXED_POLICY, FIXED_ROLE, TENANT_POLICY, build_plans, q
from .role_contract import probe_role
from .sql import FUNCTIONS

logger = logging.getLogger(__name__)

_LIVE = """
SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity,
       (SELECT obj_description(p.oid, 'pg_policy') FROM pg_policy p
         WHERE p.polrelid = c.oid AND p.polname = %s),
       EXISTS (SELECT 1 FROM pg_policy p WHERE p.polrelid = c.oid AND p.polname = %s),
       EXISTS (SELECT 1 FROM pg_policy p WHERE p.polrelid = c.oid AND p.polname NOT IN (%s, %s))
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = current_schema() AND c.relkind IN ('r', 'p')
"""


@dataclass
class SyncReport:
    applied: list = field(default_factory=list)
    unchanged: int = 0
    removed: list = field(default_factory=list)
    failed: dict = field(default_factory=dict)
    unresolvable: dict = field(default_factory=dict)


def live_state(cursor):
    cursor.execute(_LIVE, [TENANT_POLICY, FIXED_POLICY, TENANT_POLICY, FIXED_POLICY])
    return {row[0]: row[1:] for row in cursor.fetchall()}


def fixed_role_exists(cursor):
    cursor.execute("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = %s)", [FIXED_ROLE])
    return cursor.fetchone()[0]


def _apply(cursor, plan, fixed):
    table = q(plan.table)
    cursor.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    cursor.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    cursor.execute(f"DROP POLICY IF EXISTS {TENANT_POLICY} ON {table}")
    cursor.execute(f"CREATE POLICY {TENANT_POLICY} ON {table} AS PERMISSIVE FOR ALL TO PUBLIC "
                   f"USING ({plan.tenant_sql}) WITH CHECK ({plan.tenant_sql})")
    cursor.execute(f"COMMENT ON POLICY {TENANT_POLICY} ON {table} IS %s", [plan.fingerprint(fixed=fixed)])
    cursor.execute(f"DROP POLICY IF EXISTS {FIXED_POLICY} ON {table}")
    if fixed:
        cursor.execute(f"CREATE POLICY {FIXED_POLICY} ON {table} AS RESTRICTIVE FOR ALL TO {q(FIXED_ROLE)} "
                       f"USING ({plan.fixed_sql}) WITH CHECK ({plan.fixed_sql})")


def _remove(cursor, table, has_other_policies):
    cursor.execute(f"DROP POLICY IF EXISTS {TENANT_POLICY} ON {q(table)}")
    cursor.execute(f"DROP POLICY IF EXISTS {FIXED_POLICY} ON {q(table)}")
    if not has_other_policies:
        cursor.execute(f"ALTER TABLE {q(table)} NO FORCE ROW LEVEL SECURITY")
        cursor.execute(f"ALTER TABLE {q(table)} DISABLE ROW LEVEL SECURITY")


def _grant_probe(cursor):
    role = probe_role()
    if not role:
        return
    cursor.execute("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = %s)", [role])
    if not cursor.fetchone()[0]:
        cursor.execute(f"CREATE ROLE {q(role)} NOLOGIN NOSUPERUSER NOBYPASSRLS NOINHERIT")
    cursor.execute(f"GRANT USAGE ON SCHEMA public TO {q(role)}")
    cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {q(role)}")
    cursor.execute(f"GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO {q(role)}")
    cursor.execute(f"GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO {q(role)}")


def _savepoint(db, cursor, report, key, function, *args):
    try:
        with transaction.atomic(using=db.alias):
            function(cursor, *args)
        return True
    except Exception as exc:
        report.failed[key] = exc.__class__.__name__
        logger.warning("tenant_rls_sync_failed", extra={"table": key, "error": exc.__class__.__name__})
        return False


def sync(using="default"):
    db = connections[using]
    report = SyncReport()
    if db.vendor != "postgresql":
        return report
    plans, report.unresolvable = build_plans()
    with transaction.atomic(using=using), db.cursor() as cursor:
        cursor.execute("SELECT to_regclass('tenant_rls_fixedrolescope') IS NOT NULL")
        if not cursor.fetchone()[0]:
            return report  # tenant_rls is not migrated on this database (yet)
        from .pg_tools import is_scratch_database
        if is_scratch_database(cursor):
            return report
        for statement in FUNCTIONS:
            cursor.execute(statement)
        fixed = fixed_role_exists(cursor)
        live = live_state(cursor)
        wanted = {plan.table: plan for plan in plans.values()}
        for table, plan in sorted(wanted.items()):
            state = live.get(table)
            if state is None:
                continue  # model without a table here (e.g. a pending migration)
            enabled, forced, comment, has_fixed, _other = state
            if enabled and forced and comment == plan.fingerprint(fixed=fixed) and has_fixed == fixed:
                report.unchanged += 1
            elif _savepoint(db, cursor, report, table, _apply, plan, fixed):
                report.applied.append(table)
        for table, (enabled, _forced, comment, has_fixed, other) in sorted(live.items()):
            ours = (comment or "").startswith("spaceworks-rls:") or has_fixed
            if table not in wanted and ours and _savepoint(db, cursor, report, table, _remove, table, other):
                report.removed.append(table)
        _savepoint(db, cursor, report, "probe-role", _grant_probe)
    return report


def post_migrate_sync(sender, using="default", **kwargs):
    try:
        report = sync(using)
    except Exception:  # migrate must never fail on the backstop; rls_status reports the gap
        logger.exception("tenant_rls_sync_error")
        return
    if report.applied or report.removed or report.failed:
        logger.info("tenant_rls_synced", extra={
            "applied": len(report.applied), "removed": len(report.removed), "failed": len(report.failed)})
