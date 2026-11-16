"""Exclude already scheduled identities before LIMIT so later owners progress."""
from django.db.models import Exists, OuterRef, Value, CharField, BooleanField, Func
from django.db.models.functions import Cast, Concat
from apps.operations.models_reminders import ReminderSchedule


class HasUsableOffset(Func):
    output_field = BooleanField()

    def as_sql(self, compiler, connection, **kwargs):
        compiled = [compiler.compile(expr) for expr in self.source_expressions]
        offsets, due, trigger = [sql for sql, _ in compiled]
        sql = f"EXISTS (SELECT 1 FROM jsonb_array_elements_text({offsets}) AS step(value) WHERE {due} + step.value::int * interval '1 second' > {trigger})"
        return sql, [value for _, params in compiled for value in params]


def undiscovered(rows, *, space, source, prefix, due_field, exact=False):
    rows = rows.annotate(_reminder_prefix=prefix)
    existing = ReminderSchedule.objects.filter(makerspace=space, source=source,
        due_at=OuterRef(due_field), **{"subject" if exact else "subject__startswith": OuterRef("_reminder_prefix")})
    # schedule_reminders creates all offsets in one transaction. An existing
    # subject therefore means all its steps already have durable schedules.
    return rows.annotate(_already_scheduled=Exists(existing)).filter(_already_scheduled=False)


def stage_prefix():
    return Concat(Value("stage-assignment:"), Cast("pk", CharField()), Value(":due:"), Cast("due_revision", CharField()))
