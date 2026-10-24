"""Typed stage target for F's immutable revision appender and shared registry."""
from dataclasses import dataclass
from apps.events.programme.providers import FormProvider, append_stage_revision_locked
from apps.payments.event_payouts.errors import require
from .definition_models import EventStageForm
from .policy import require_stage_schema


@dataclass(frozen=True)
class StageTarget:
    pk: int
    event_id: int
    form_id: str
    current_revision_id: int | None


def append_locked(*, event, actor, target, schema):
    require_stage_schema(schema)
    descriptor = StageTarget(target.pk, target.event_id, str(target.form_id), target.current_revision_id)
    return append_stage_revision_locked(event=event, actor=actor, target=descriptor, schema=schema)


def resolve(*, event, selector_id, **kwargs):
    return EventStageForm.objects.get(pk=selector_id, event=event)


def read(*, target, **kwargs):
    return target.current_revision.schema if target.current_revision_id else None


STAGE_FORM_PROVIDER = FormProvider("stage", resolve, read, append_locked)
