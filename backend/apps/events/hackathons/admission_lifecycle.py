"""Existing cancellation/termination calls this under G's existing lock context."""
from django.utils.translation import gettext
from django.shortcuts import get_object_or_404
from django.utils import timezone
from apps.events.models import Event
from .admission_errors import fail
from .admission_models import HackathonApplication, HackathonConfig, HackathonApplicationCohort
from .admission_transactions import assert_locked, CommandContext, lock_domain_parents, record, notice
from .admission_workflow import transition_registration_locked


def context_locked(event, actor, locks):
    assert_locked(locks, event.pk)
    config = HackathonConfig.objects.filter(event=event).first()
    if config is None:
        return None
    lock_domain_parents(event.pk)
    return CommandContext(event, config, actor, locks, None, None)


def promote_event_locked(*, event, actor, locks):
    ctx = context_locked(event, actor, locks)
    if ctx is not None:
        from .admission_promotion import promote_locked
        return promote_locked(ctx)


def cancel_registration_locked(*, event, registration, actor, member_cancel, locks):
    """Legacy cancellation still terminates the entire sealed cohort atomically."""
    from apps.events.cancellation_policy import member_can_cancel
    from .admission_rsvp import subject_applications_locked, end_group_locked
    app = HackathonApplication.objects.filter(event=event, registration=registration).first()
    if app is None:
        from apps.events.contributions.models_admission import EventContributorAdmission
        if EventContributorAdmission.objects.filter(event=event, registration=registration).exists():
            return False
        if HackathonConfig.objects.filter(event=event, enabled=True).exists():
            fail("admission_mapping_conflict", gettext("The registration needs staff reconciliation."))
        return False
    if member_cancel and (actor is None or actor.pk != app.member_id or not member_can_cancel(registration)):
        fail("invalid_transition", gettext("The member cancellation deadline has passed."))
    from apps.events.models import EventRegistration
    ctx = context_locked(event, actor, locks)
    cohort, applications = subject_applications_locked(app)
    if not cohort:
        applications = [HackathonApplication.objects.select_for_update().get(pk=app.pk)]
    if EventRegistration.objects.filter(pk__in=[a.registration_id for a in applications], status="attended").exists():
        fail("invalid_transition", gettext("An attended application cannot be cancelled."))
    end_group_locked(ctx, applications, "withdrawn", reason_code="registration_cancelled")
    if cohort:
        cohort.state, cohort.version = "withdrawn", cohort.version + 1
        cohort.save()
        record(ctx, "cohort_event_cancelled", cohort, version=cohort.version)
    from .admission_promotion import promote_locked
    promote_locked(ctx, exclude_application_ids=tuple(a.pk for a in applications))
    registration.refresh_from_db()
    return True


def require_attendance_mapping(registration):
    app = HackathonApplication.objects.filter(registration=registration).first()
    if app is not None and app.state != "confirmed":
        fail("admission_mapping_conflict", gettext("Confirm this application before check-in."))
    from apps.events.contributions.models_admission import EventContributorAdmission
    contributor = EventContributorAdmission.objects.filter(event_id=registration.event_id, registration=registration).exists()
    if app is None and not contributor and HackathonConfig.objects.filter(event_id=registration.event_id, enabled=True).exists():
        fail("admission_mapping_conflict", gettext("The registration needs staff reconciliation."))


def attendance_changed_locked(*, event, registration, actor, locks):
    from .admission_bridge import assert_registration_mapping
    app = HackathonApplication.objects.filter(registration=registration, event=event).first()
    if app is None:
        return
    assert_registration_mapping(application_id=app.pk)
    # Submission checks attendance from the canonical registration on every attempt.
    # A correction invalidates previously read application/team projections too.
    app.version += 1
    app.save(update_fields=["version"])
    from .team_models import HackathonTeam, HackathonTeamMember
    team_ids = HackathonTeamMember.objects.filter(application=app, state="active").values_list("team_id", flat=True)
    ctx = context_locked(event, actor, locks)
    for team in HackathonTeam.objects.select_for_update().filter(pk__in=team_ids).order_by("pk"):
        team.version += 1
        team.save(update_fields=["version"])
        record(ctx, "team_updated", team, version=team.version)


def close_event_locked(*, event, actor, locks):
    """Close freezes editable sources without making an admission decision."""
    ctx = context_locked(event, actor, locks)
    if ctx is None:
        return
    from .admission_answers import lock_answers_locked
    for app in HackathonApplication.objects.select_for_update().filter(event=event,
            state__in=("submitted", "offered", "waitlisted", "confirmed"), answer_locked_at__isnull=True).order_by("pk"):
        lock_answers_locked(ctx, app, closing=True)


def cancel_event_locked(*, event_id, actor, locks):
    assert_locked(locks, event_id)
    event = get_object_or_404(Event, pk=event_id)
    if event.status != "cancelled":
        fail("invalid_transition", gettext("Cancel the event through its lifecycle first."))
    config = HackathonConfig.objects.filter(event=event).first()
    if config is None:
        return
    close_event_locked(event=event, actor=actor, locks=locks)
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
