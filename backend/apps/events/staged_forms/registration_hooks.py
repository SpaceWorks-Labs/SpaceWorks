"""G calls after canonical registration parents and before the outer receipt."""
from apps.events.contracts.form_operations import child_form_operation_id
from apps.payments.event_payouts.errors import require
from .definition_models import EventStageForm
from .stage_workflow import activate_locked
from .trigger_service import Participant
from .transactions import require_outer


def activate_for_participant_locked(*, event, registration, actor, locks, application=None, outer_operation_id=None):
    require_outer(locks, event)
    require(registration.event_id == event.pk and registration.member_id == actor.pk, "invalid_subject", status=404)
    rows = []
    for definition in EventStageForm.objects.select_for_update().filter(event=event, state="published").order_by("pk"):
        creation_id = child_form_operation_id(outer_operation_id, event_id=event.pk, owner_id=actor.pk,
            slot=f"stage:{definition.pk}") if outer_operation_id else None
        subject = Participant(event, actor.pk, registration, application, creation_id)
        assignment = activate_locked(definition=definition, subject=subject, locks=locks)
        if assignment:
            rows.append(assignment)
    return rows
