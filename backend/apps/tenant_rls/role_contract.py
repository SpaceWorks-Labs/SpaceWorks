"""A0 role contract: which RLS mode the runtime database role can honour (#128 C-25).

Postgres never applies a policy to a superuser or a BYPASSRLS role, and the generated
policies bind a table owner only through FORCE. So the mode is decided by who the app
connects as, never by refusing to start:

* ``enforce`` - a narrow runtime role (the bundled compose ``spaceworks_app``): rows
  outside the bound scope are invisible and cannot be written.
* ``report`` - the app connects as the owner role (common on free-tier Postgres that
  cannot make roles): every row stays visible and the first out-of-scope row in each
  transaction is reported (``rls.report_only_violation``); ``/control/`` warns.
* ``inactive`` - a superuser or BYPASSRLS role: policies cannot bind at all; ``/control/``
  warns. The boundary sends nothing.
* ``off`` - ``TENANT_RLS_MODE=off``: the operator's escape hatch; the boundary sends nothing.

``TENANT_RLS_PROBE_ROLE`` (tests and the release regression only) makes every bound
statement ``SET LOCAL ROLE`` to a narrow probe role, so a superuser test run is forced on.
"""

import logging
from dataclasses import dataclass

from django.conf import settings
from django.core.signals import setting_changed
from django.db import connections

logger = logging.getLogger(__name__)
_cache = {}
SETTINGS = ("TENANT_RLS_MODE", "TENANT_RLS_PROBE_ROLE")
MODES = ("auto", "enforce", "report", "off")


@dataclass(frozen=True)
class Contract:
    role: str
    superuser: bool
    bypassrls: bool
    owns_scoped_tables: bool

    @property
    def narrow(self):
        return not (self.superuser or self.bypassrls or self.owns_scoped_tables)


def configured_mode():
    value = (getattr(settings, "TENANT_RLS_MODE", "auto") or "auto").strip().lower()
    return value if value in MODES else "auto"


def probe_role():
    return (getattr(settings, "TENANT_RLS_PROBE_ROLE", "") or "").strip()


def inspect(raw_connection):
    """Read the contract with a raw DB-API cursor (never through the RLS wrapper)."""
    with raw_connection.cursor() as cursor:
        cursor.execute(
            "SELECT current_user::text, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
        role, superuser, bypassrls = cursor.fetchone()
        cursor.execute(
            "SELECT EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = current_schema() AND c.relkind IN ('r', 'p') AND c.relrowsecurity "
            "AND pg_has_role(current_user, c.relowner, 'USAGE'))")
        owns = cursor.fetchone()[0]
    return Contract(role=role, superuser=bool(superuser), bypassrls=bool(bypassrls), owns_scoped_tables=bool(owns))


def decide(contract, mode=None, probe=None):
    mode = configured_mode() if mode is None else mode
    probe = probe_role() if probe is None else probe
    if mode == "off":
        return "off"
    if probe:
        return "report" if mode == "report" else "enforce"
    if contract is None or contract.superuser or contract.bypassrls:
        return "inactive"
    if contract.owns_scoped_tables:
        return "enforce" if mode == "enforce" else "report"
    return "report" if mode == "report" else "enforce"


def effective_mode(db):
    """The cached mode for one Django connection alias; never raises."""
    key = (db.alias, configured_mode(), probe_role())
    if key in _cache:
        return _cache[key]
    if key[1] == "off":
        _cache[key] = "off"
        return "off"
    try:
        db.ensure_connection()
        contract = inspect(db.connection)
    except Exception:  # an unreachable database is not a reason to stop serving
        logger.warning("tenant_rls_role_contract_unavailable", extra={"alias": db.alias})
        return "inactive"
    mode = decide(contract)
    _cache[key] = mode
    if mode in {"report", "inactive"}:
        logger.warning("tenant_rls_not_enforced", extra={"alias": db.alias, "mode": mode, "role": contract.role})
    return mode


def statement_mode(db):
    """``enforce``/``report`` when bound statements must carry settings, else ``None``."""
    if db.vendor != "postgresql":
        return None
    mode = effective_mode(db)
    return mode if mode in {"enforce", "report"} else None


def status(alias="default"):
    db = connections[alias]
    try:
        db.ensure_connection()
        contract = inspect(db.connection)
    except Exception:
        return {"mode": "inactive", "configured": configured_mode(), "contract": None}
    return {"mode": decide(contract), "configured": configured_mode(), "contract": contract}


def reset_cache(**kwargs):
    if kwargs.get("setting") in (None, *SETTINGS):
        _cache.clear()


setting_changed.connect(reset_cache)
