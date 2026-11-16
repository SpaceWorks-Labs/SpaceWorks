"""Insert ordering for portable stage, reimbursement and payout rows.

Their relational guard triggers check, at INSERT time, that every non-null pointer names
an existing row in the same tenant and event scope. FK constraints are deferred, but
those triggers are not, so two things are arranged here:

* a nullable pointer to a model inserted later (``ReimbursementClaim.current_revision``,
  ``EventPayoutObligation.current_revision``, ``StageFormAssignment.completed_response``
  and similar) is inserted NULL and set by one UPDATE after every row exists; and
* rows of a model with a self pointer (``EventPayoutEntry.amends``, ``PayoutHold.releases``,
  ``EventPayoutObligationRevision.previous_revision``) are inserted parents first.

Only the packages' portable models are affected; every other model keeps the
importer's original single-INSERT behaviour.
"""
from django.db import connection

from .catalog_reimbursements import PORTABLE_MODELS


def _self_fields(model):
    return [field for field in model._meta.local_concrete_fields
            if field.is_relation and field.null and field.related_model is model]


class PointerDeferral:
    def __init__(self, ordered):
        self.position = {model._meta.label: index for index, model in enumerate(ordered)}
        self.pending = []

    @classmethod
    def begin(cls, ordered):
        """Mark this import transaction for guards that admit imported history.

        Transaction-local: the attendance-correction guard then checks identity but
        not the live "current revision" rule, which later check-ins legitimately moved.
        """
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL app.tenant_import = 'on'")
        return cls(ordered)

    def source_rows(self, model, rows):
        fields = _self_fields(model) if model._meta.label in PORTABLE_MODELS else []
        if not fields:
            return rows
        rows = list(rows)
        pk = model._meta.pk.attname
        by_pk = {str(row[pk]): row for row in rows}
        ordered, placed = [], set()

        def place(row, trail=()):
            key = str(row[pk])
            if key in placed:
                return
            if key in trail:
                raise ValueError(f"{model._meta.label} rows form a pointer cycle.")
            for field in fields:
                parent = row.get(field.attname)
                if parent not in (None, "") and str(parent) in by_pk:
                    place(by_pk[str(parent)], (*trail, key))
            placed.add(key)
            ordered.append(row)

        for row in rows:
            place(row)
        return ordered

    def defer(self, model, row):
        label = model._meta.label
        if label not in PORTABLE_MODELS:
            return
        here = self.position[label]
        for field in model._meta.local_concrete_fields:
            if (field.is_relation and field.null and field.related_model is not None
                    and self.position.get(field.related_model._meta.label, -1) > here
                    and row[field.column] is not None):
                self.pending.append((model, row[model._meta.pk.column], field.column, row[field.column]))
                row[field.column] = None

    def apply(self):
        quote = connection.ops.quote_name
        with connection.cursor() as cursor:
            for model, pk, column, value in self.pending:
                cursor.execute(
                    f"UPDATE {quote(model._meta.db_table)} SET {quote(column)} = %s WHERE {quote(model._meta.pk.column)} = %s",
                    [value, pk])
        applied, self.pending = len(self.pending), []
        return applied
