"""A1 context boundary on the wire: every bound statement carries its own settings.

Each statement executed under a binding is sent as one simple-protocol string whose
first statement sets the four ``app.*`` settings with ``is_local = true``. Outside an
explicit transaction the pair runs as one implicit transaction, so the values die with
the statement; inside one they last until commit or rollback and are re-sent by every
later statement. Nothing is ever left on a pooled server connection, which is what makes
this safe under ``CONN_MAX_AGE > 0`` and transaction-mode poolers (PgBouncer, Supabase
:6543). Leaving a binding inside a still-open transaction resets the values explicitly;
if that reset fails the connection is closed (or, inside ``atomic``, marked for rollback).

Server-side cursors cannot carry a prefix (``DECLARE`` takes one statement), so they get
the settings through a separate statement; with autocommit that is session-level and is
reset as soon as the binding ends. Transaction-control statements are never prefixed:
``ROLLBACK TO SAVEPOINT`` must run in an aborted transaction.
"""

import re

from django.db import connections

from .context import current
from .role_contract import probe_role, statement_mode

_TRANSACTION_CONTROL = ("SAVEPOINT", "RELEASE", "ROLLBACK", "COMMIT", "BEGIN", "START TRANSACTION")
_SAFE_VALUE = re.compile(r"^[a-z0-9_,]*$")
_SAFE_ROLE = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
_NAMES = ("app.rls_bound", "app.makerspace_id", "app.rls_capability", "app.rls_mode")
RESET_LOCAL = "SELECT " + ", ".join(f"set_config('{name}', '', true)" for name in _NAMES)
RESET_SESSION = "SELECT " + ", ".join(f"set_config('{name}', '', false)" for name in _NAMES)


def _settings_sql(binding, mode, *, local=True):
    values = binding.guc_values(mode)
    if any(not _SAFE_VALUE.match(value) for value in values.values()):
        raise ValueError("Unsafe RLS setting value.")
    flag = "true" if local else "false"
    return "SELECT " + ", ".join(f"set_config('{name}', '{value}', {flag})" for name, value in values.items())


def _role_sql(*, local=True):
    role = probe_role()
    if not role:
        return ""
    if not _SAFE_ROLE.match(role):
        raise ValueError("Unsafe TENANT_RLS_PROBE_ROLE.")
    return f'SET {"LOCAL " if local else ""}ROLE "{role}"'


def prefix(binding, mode):
    parts = [part for part in (_role_sql(), _settings_sql(binding, mode)) if part]
    return "; ".join(parts) + "; "


def _in_transaction(db):
    return db.in_atomic_block or not db.autocommit


def rls_execute_wrapper(execute, sql, params, many, context):
    binding = current()
    if binding is None or not isinstance(sql, str):
        return execute(sql, params, many, context)
    db = context["connection"]
    mode = statement_mode(db)
    if mode is None or sql.lstrip()[:20].upper().startswith(_TRANSACTION_CONTROL):
        return execute(sql, params, many, context)
    raw_cursor = getattr(context.get("cursor"), "cursor", None)
    if getattr(raw_cursor, "name", None):
        _apply_separately(db, binding, mode)
        return execute(sql, params, many, context)
    if _in_transaction(db):
        db._tenant_rls_dirty = True
    return execute(prefix(binding, mode) + sql, params, many, context)


def _apply_separately(db, binding, mode):
    local = _in_transaction(db)
    statements = [part for part in (_role_sql(local=local), _settings_sql(binding, mode, local=local)) if part]
    with db.connection.cursor() as cursor:
        for statement in statements:
            cursor.execute(statement)
    if local:
        db._tenant_rls_dirty = True
    else:
        db._tenant_rls_session_dirty = True


def install(connection, **kwargs):
    """``connection_created`` receiver: one permanent wrapper per connection object."""
    if connection.vendor == "postgresql" and rls_execute_wrapper not in connection.execute_wrappers:
        connection.execute_wrappers.append(rls_execute_wrapper)


def release_connections():
    """Reset whatever a finished binding left on this thread's open connections."""
    for db in connections.all(initialized_only=True):
        dirty = getattr(db, "_tenant_rls_dirty", False)
        session = getattr(db, "_tenant_rls_session_dirty", False)
        if not (dirty or session):
            continue
        db._tenant_rls_dirty = db._tenant_rls_session_dirty = False
        if db.connection is None:
            continue
        try:
            with db.connection.cursor() as cursor:
                if session:
                    cursor.execute(RESET_SESSION)
                    if probe_role():
                        cursor.execute("RESET ROLE")
                if dirty and _in_transaction(db):
                    cursor.execute(RESET_LOCAL)
                    if probe_role():
                        cursor.execute("SET LOCAL ROLE NONE")
        except Exception:
            if db.in_atomic_block:
                db.needs_rollback = True
            else:
                db.close()
