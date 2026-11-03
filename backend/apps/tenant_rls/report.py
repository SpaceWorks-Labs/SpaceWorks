"""Report-only mode: turn the policies' NOTICEs into sampled audit rows (#128 C-25).

In ``report`` mode a policy that meets a row outside the bound scope admits it and raises
one ``spaceworks_rls_violation <table>`` NOTICE per transaction. psycopg2 keeps notices
on the connection; the boundary drains ours after each request or task and records
``rls.report_only_violation`` (first per table and path in a process, then sampled).
"""

import logging
from collections import Counter
from threading import Lock

from django.db import connections, transaction

logger = logging.getLogger(__name__)
MARKER = "spaceworks_rls_violation"
SAMPLE_EVERY = 500
_counts = Counter()
_lock = Lock()


def _drain(db):
    raw = getattr(db, "connection", None)
    notices = getattr(raw, "notices", None)
    if not notices:
        return []
    ours = [line for line in notices if MARKER in line]
    if ours:
        notices[:] = [line for line in notices if MARKER not in line]
    return [line.split(MARKER, 1)[1].strip() for line in ours]


def flush(*, label=""):
    for db in connections.all(initialized_only=True):
        try:
            tables = _drain(db)
        except Exception:
            continue
        for table in sorted(set(tables)):
            with _lock:
                _counts[(table, label)] += 1
                count = _counts[(table, label)]
            if count != 1 and count % SAMPLE_EVERY:
                continue
            logger.warning("tenant_rls_report_only_violation", extra={"table": table, "path": label})
            try:
                from apps.audit.services import record
                with transaction.atomic(using=db.alias):
                    record(None, "rls.report_only_violation", makerspace=None,
                           meta={"table": table[:63], "path": label[:200]}, using=db.alias)
            except Exception:
                logger.warning("tenant_rls_report_audit_failed", extra={"table": table})


def reset_sampling():
    with _lock:
        _counts.clear()
