"""Advisory-lock namespaces and the dedicated lock connection.

Namespace 734410 is reserved for cloud tick task exclusion (734411 for full
scheduler leadership). Stable SHA-256 signed-int32 keys never use Python hash().
A collision only serializes unrelated work; it cannot permit duplicate execution.
"""
import hashlib

import psycopg2
from django.db import connections

from .contracts import GuardLost

TICK_NAMESPACE = 734_410
LEADER_NAMESPACE = 734_411


def task_lock_key(key):
    return int.from_bytes(hashlib.sha256(key.encode("ascii")).digest()[:4], "big", signed=True)


def new_connection(timeout=5):
    # M's validated Django connection builder preserves provider TLS parameters.
    try:
        params = connections["default"].get_connection_params()
        params["connect_timeout"] = max(1, min(5, int(timeout)))
        return psycopg2.connect(**params)
    except Exception:
        raise GuardLost() from None
