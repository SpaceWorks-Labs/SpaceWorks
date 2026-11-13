"""Refuse venue debts the portable importer would otherwise silently drop."""
from django.db import connection, transaction

from .insertion_errors import VenueFeeDebtProvenanceUnavailable
from .reference_state import ReferenceState, TABLE_NAME

_BATCH_SIZE = 500


def _check(references, ids):
    if references.has_any("payments.Payment", ids, "subject_id"):
        raise VenueFeeDebtProvenanceUnavailable()


def refuse_orphan_venue_payments(archive):
    """Use the importer's transaction-local index before object or target writes.

    A nested savepoint isolates this temporary table from a surrounding transaction.
    An exception rolls back the table creation; success explicitly drops it so a later
    ReferenceState in the caller's still-open transaction can use the same name.
    """
    with transaction.atomic():
        references = ReferenceState(archive)
        ids = []
        for row in archive.raw_rows("payments.Payment"):
            if row.get("subject_type") != "event_venue_fee":
                continue
            ids.append(str(row["id"]))
            if len(ids) == _BATCH_SIZE:
                _check(references, ids)
                ids.clear()
        if ids:
            _check(references, ids)
        with connection.cursor() as cursor:
            cursor.execute(f"DROP TABLE {TABLE_NAME}")
