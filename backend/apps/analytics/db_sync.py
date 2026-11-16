"""Build the analytics database objects after every migrate (``manage.py analytics_sync``).

Runs as the migrating role, which owns the tables. It creates the NOLOGIN roles, the three
schemas, the provisioning functions and every curated view for both audiences, then stamps
a fingerprint so an unchanged deployment costs two catalog reads. It never fails a migrate:
a database whose owner cannot create roles (some managed and free-tier hosts) is skipped
and the console reports analytics as not available on this hosting.

A migrate that changes the schema first drops the views (``pre_migrate_drop``), because a
view blocks ALTERs of the columns it reads; they are rebuilt right after.
"""

import hashlib
import logging
import os
from dataclasses import dataclass, field
from urllib.parse import unquote, urlparse

from django.db import connections, transaction

from . import db_ddl
from .catalogue.registry import VIEWS_VERSION, installed_views
from .catalogue.render import PLATFORM, SPACE, catalog_sql, render
from .db_functions import FUNCTIONS
from .db_names import PLATFORM_SCHEMA, SPACE_SCHEMA, roles

logger = logging.getLogger(__name__)
GENERATOR_VERSION = "1"


@dataclass
class SyncResult:
    state: str = "skipped"
    reason: str = ""
    views: int = 0
    failed: dict = field(default_factory=dict)


def plan(views):
    """[(schema, name, sql, owner key, reader key)] for every view of both audiences."""
    rows = []
    for view in views:
        rows.append((SPACE_SCHEMA, view.name, render(view, SPACE), "powner" if view.lookup else "owner", "reader"))
        rows.append((PLATFORM_SCHEMA, view.name, render(view, PLATFORM), "powner", "preader"))
    catalog = catalog_sql(views, VIEWS_VERSION)
    rows.append((SPACE_SCHEMA, "views_catalog", catalog, "powner", "reader"))
    rows.append((PLATFORM_SCHEMA, "views_catalog", catalog, "powner", "preader"))
    return rows


def fingerprint(rows, names, callers):
    body = "\n".join([GENERATOR_VERSION, str(VIEWS_VERSION), *sorted(names.values()), *sorted(callers),
                      *FUNCTIONS, *(f"{s}.{n}:{o}:{r}:{sql}" for s, n, sql, o, r in rows)])
    return "spaceworks-analytics:" + hashlib.sha256(body.encode("utf-8")).hexdigest()


def runtime_callers(cursor):
    """Roles that may call the provisioning functions: the runtime role named by
    SPACEWORKS_RUNTIME_DATABASE_URL (migrate runs with the owner URL) and L8's probe role."""
    from apps.tenant_rls.role_contract import probe_role

    callers = set()
    url = os.environ.get("SPACEWORKS_RUNTIME_DATABASE_URL", "")
    user = unquote(urlparse(url).username or "") if url else ""
    for role in (user, probe_role()):
        if role and db_ddl.role_exists(cursor, role):
            callers.add(role)
    cursor.execute("SELECT current_user::text")
    callers.discard(cursor.fetchone()[0])
    return sorted(callers)


def _ready(cursor):
    from apps.tenant_rls.pg_tools import is_scratch_database

    cursor.execute("SELECT to_regclass('tenant_rls_fixedrolescope') IS NOT NULL "
                   "AND to_regclass('analytics_analyticsconnection') IS NOT NULL")
    if not cursor.fetchone()[0]:
        return "not_migrated"
    if is_scratch_database(cursor):
        return "scratch_database"
    superuser, createrole, version = db_ddl.privileges(cursor)
    if not (superuser or createrole):
        return "cannot_create_roles"
    if not superuser and version < 160000:
        return "postgres_16_required"
    return ""


def sync(using="default", *, force=False):
    db = connections[using]
    result = SyncResult()
    if db.vendor != "postgresql":
        result.reason = "not_postgresql"
        return result
    with db.cursor() as cursor:
        result.reason = _ready(cursor)
        if result.reason:
            return result
        cursor.execute("SELECT current_database()")
        names = roles(cursor.fetchone()[0])
        rows = plan(installed_views())
        callers = runtime_callers(cursor)
        stamp = fingerprint(rows, names, callers)
        expected = {(schema, name): owner for schema, name, _sql, owner, _reader in rows}
        if not force and db_ddl.read_fingerprint(cursor) == stamp and db_ddl.owners_intact(cursor, names, expected):
            result.state, result.views = "unchanged", len(rows)
            return result
        superuser, _createrole, _version = db_ddl.privileges(cursor)
        with transaction.atomic(using=using):
            created_fixed = db_ddl.ensure_roles(cursor, names, superuser=superuser)
            db_ddl.drop_view_schemas(cursor)
            db_ddl.ensure_schemas(cursor, names)
            db_ddl.grant_base(cursor, names)
            db_ddl.ensure_functions(cursor, callers)
            for schema, name, sql, owner, reader in rows:
                try:
                    with transaction.atomic(using=using):
                        db_ddl.create_view(cursor, schema, name, sql, names[owner], names[reader])
                    result.views += 1
                except Exception as exc:  # one broken view never blocks the others
                    result.failed[f"{schema}.{name}"] = f"{exc.__class__.__name__}: {str(exc).strip()[:160]}"
            db_ddl.write_fingerprint(cursor, "" if result.failed else stamp)
    if created_fixed:
        from apps.tenant_rls.sync import sync as rls_sync
        rls_sync(using)  # the RESTRICTIVE fixed-role policy exists only once the group does
    result.state = "synced"
    return result


def post_migrate_sync(sender, using="default", **kwargs):
    try:
        result = sync(using)
    except Exception:  # migrate must never fail on analytics; the console reports it unavailable
        logger.exception("analytics_sync_error")
        return
    if result.failed:
        logger.warning("analytics_views_failed", extra={"failed": sorted(result.failed)})
    elif result.state == "skipped" and result.reason not in {"not_postgresql", "not_migrated", "scratch_database"}:
        logger.info("analytics_sync_skipped", extra={"reason": result.reason})


def pre_migrate_drop(sender, using="default", plan=None, **kwargs):
    """Drop the curated views before a migrate that will change the schema."""
    if not plan:
        return
    db = connections[using]
    if db.vendor != "postgresql":
        return
    try:
        with db.cursor() as cursor, transaction.atomic(using=using):
            db_ddl.drop_view_schemas(cursor)
    except Exception:
        logger.exception("analytics_pre_migrate_drop_error")
