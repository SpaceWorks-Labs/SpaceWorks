"""G calls after canonical registration parents and before the outer receipt."""
from apps.events.contracts.form_operations import child_form_operation_id
from apps.payments.event_payouts.errors import require
from .definition_models import EventStageForm
from .stage_workflow import activate_locked
from .trigger_service import Participant
from .transactions import require_outer, lock_stage_parents


def activate_for_participant_locked(*, event, registration, actor, locks, application=None, outer_operation_id=None):
    require_outer(locks, event)
    require(registration.event_id == event.pk and registration.member_id == actor.pk, "invalid_subject", status=404)
    require(application is None or (application.event_id == event.pk and application.member_id == actor.pk
        and application.registration_id == registration.pk), "invalid_subject", status=404)
    lock_stage_parents(event=event, owner_ids=(actor.pk,))
    rows = []
    for definition in EventStageForm.objects.select_for_update().filter(event=event, state="published").order_by("pk"):
        creation_id = child_form_operation_id(outer_operation_id, event_id=event.pk, owner_id=actor.pk,
            slot=f"stage:{definition.pk}") if outer_operation_id else None
        subject = Participant(event, actor.pk, registration, application, creation_id)
        assignment = activate_locked(definition=definition, subject=subject, locks=locks)
        if assignment:
            rows.append(assignment)
    from .lifecycle import reconcile_participant_locked
    reconcile_participant_locked(subject=Participant(event, actor.pk, registration, application), locks=locks)
    return rows


def prepare_inline(**kwargs):
    from .inline_submission import prepare_inline as run
    return run(**kwargs)


def bind_inline_locked(**kwargs):
    from .inline_submission import bind_locked
    return bind_locked(**kwargs)


from .lifecycle import cancel_participant_locked, reschedule_event_locked
