"""Existing cancellation/termination calls this under G's existing lock context."""
from django.shortcuts import get_object_or_404
from django.utils import timezone
from apps.events.models import Event
from .admission_errors import fail
from .admission_models import HackathonApplication, HackathonConfig, HackathonApplicationCohort
from .admission_transactions import assert_locked, CommandContext, lock_domain_parents, record, notice
from .admission_workflow import transition_registration_locked


def cancel_event_locked(*, event_id, actor, locks):
    assert_locked(locks, event_id)
    event = get_object_or_404(Event, pk=event_id)
    if event.status != "cancelled":
        fail("invalid_transition", "Cancel the event through its lifecycle first.")
    config = HackathonConfig.objects.filter(event=event).first()
    if config is None:
        return
    lock_domain_parents(event_id)
    ctx = CommandContext(event, config, actor, locks, None, None)
    for app in HackathonApplication.objects.select_for_update().filter(event=event,
            state__in=("submitted", "offered", "waitlisted", "confirmed")).order_by("pk"):
        transition_registration_locked(application_id=app.pk, registration_id=app.registration_id,
            transition="event_cancel", actor=actor, reason_code="event_cancelled", locks=locks)
        old = app.state
        app.state, app.response_at, app.version = "withdrawn", timezone.now(), app.version + 1
        app.save()
        record(ctx, "application_event_cancelled", app, old_state=old, new_state=app.state)
        notice(ctx, app, "event_cancelled")
        from .team_lifecycle import eligibility_changed_locked
        eligibility_changed_locked(ctx, app)
    for cohort in HackathonApplicationCohort.objects.filter(event=event).exclude(state__in=("withdrawn", "rejected", "expired", "declined")):
        cohort.state, cohort.version = "withdrawn", cohort.version + 1
        cohort.save()
        record(ctx, "cohort_event_cancelled", cohort, version=cohort.version)
