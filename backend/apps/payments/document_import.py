"""Exact-row INSERT authority used only by controlled archive reconstruction."""

from contextlib import contextmanager
import json

from django.db import DatabaseError

GUC = "app.payment_document_import_ids"


@contextmanager
def document_import_rows(cursor, model, ids):
    if model._meta.label != "payments.PaymentDocument":
        yield
        return
    if cursor.db.get_autocommit() or not cursor.db.in_atomic_block:
        raise RuntimeError("Document reconstruction requires a caller-owned transaction.")
    cursor.execute("SELECT current_setting(%s, true)", [GUC])
    previous = cursor.fetchone()[0] or ""
    cursor.execute("SELECT set_config(%s, %s, true)", [GUC, json.dumps([int(pk) for pk in ids])])
    database_failed = False
    try:
        yield
    except DatabaseError:
        database_failed = True
        raise
    finally:
        # A failed statement leaves the transaction unusable; its savepoint rollback
        # restores the old LOCAL setting as well as the INSERT itself.
        if not database_failed and not cursor.db.needs_rollback:
            cursor.execute("SELECT set_config(%s, %s, true)", [GUC, previous])
