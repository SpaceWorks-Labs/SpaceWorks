"""Sealed team-together identity and atomic cohort submission."""
from django.utils.translation import gettext
import hashlib
import json
from django.utils import timezone
from .admission_errors import fail
from .admission_models import HackathonApplication, HackathonApplicationCohort
from .admission_transactions import record


def roster_hash(members):
    value = sorted((m.member_id, m.application_id) for m in members)
    return hashlib.sha256(json.dumps(value, separators=(",", ":")).encode()).hexdigest()


def require_sealed_roster(team, members):
    cohort = HackathonApplicationCohort.objects.filter(team=team, event_id=team.event_id).first()
    if not cohort or not cohort.sealed_roster_hash or roster_hash(members) != cohort.sealed_roster_hash:
        fail("roster_changed", gettext("The team roster changed. Every member must review and resubmit."))
    if set(cohort.applications.values_list("member_id", flat=True)) != {m.member_id for m in members}:
        fail("roster_changed", gettext("The application roster no longer matches the team."))
    return cohort


def seal_locked(ctx, team):
    if ctx.config.team_mode != "team_together":
        fail("invalid_transition", gettext("Only team applications use a sealed cohort."))
    members = list(team.memberships.select_for_update().filter(state="active").order_by("pk"))
    if not ctx.config.team_min <= len(members) <= ctx.config.team_max:
        fail("team_size_required", gettext("Complete the required team size first."))
    cohort, _ = HackathonApplicationCohort.objects.get_or_create(event=ctx.event, team=team)
    if cohort.state not in ("draft", "declined", "expired", "withdrawn", "rejected"):
        fail("invalid_transition", gettext("This cohort is already submitted."))
    from .admission_workflow import require_application_open
    require_application_open(ctx.event, ctx.config, timezone.now())
    applications = list(HackathonApplication.objects.select_for_update().filter(
        pk__in=[m.application_id for m in members], event=ctx.event).order_by("pk"))
    if len(applications) != len(members) or any(a.state != "submitted" or a.coc_revision != ctx.config.coc_revision for a in applications):
        fail("cohort_incomplete", gettext("Every member must submit their own application and current code of conduct."))
    if any(a.cohort_id and a.cohort_id != cohort.pk for a in applications):
        fail("roster_changed", gettext("An application belongs to another cohort."))
    cohort.sealed_roster_hash, cohort.sealed_at = roster_hash(members), timezone.now()
    cohort.state, cohort.version = "submitted", cohort.version + 1
    cohort.save()
    for app in applications:
        from .admission_answers import lock_answers_locked, require_date_reviewed
        require_date_reviewed(app)
        lock_answers_locked(ctx, app)
        app.cohort, app.version = cohort, app.version + 1
        app.save()
        record(ctx, "application_cohort_sealed", app, cohort_id=cohort.pk, version=app.version)
    record(ctx, "cohort_submitted", cohort, people=len(members), roster_hash=cohort.sealed_roster_hash)
    if ctx.config.review_mode == "auto":
        from .review_models import ApplicationDecision, ApplicationDecisionBatch
        from .admission_decisions import release_decision_locked
        from .capacity_admission import occupancy
        batch = ApplicationDecisionBatch.objects.create(event=ctx.event, actor=ctx.actor)
        left = occupancy(ctx.event, ctx.config)["offer_spots_left"]
        decision = ApplicationDecision.objects.create(batch=batch, cohort=cohort,
            outcome="offer" if left is None or left >= len(members) else "waitlist",
            reason_code="automatic_review", expected_subject_version=cohort.version)
        release_decision_locked(ctx, decision, auto=True)
        batch.state, batch.committed_at = "committed", timezone.now()
        batch.save()
    return cohort


def invalidate_locked(ctx, team):
    cohort = HackathonApplicationCohort.objects.filter(team=team).first()
    if not cohort or not cohort.sealed_roster_hash:
        return
    if cohort.state in ("offered", "confirmed"):
        fail("team_locked", gettext("An offered or confirmed cohort requires staff reopening."))
    cohort.state, cohort.sealed_roster_hash = "draft", ""
    cohort.version += 1
    cohort.save()
    for app in cohort.applications.select_for_update().order_by("pk"):
        from .admission_answers import archive_locked
        archive_locked(ctx, app)
        app.cohort, app.state, app.answer_locked_at = None, "draft", None
        app.version += 1
        app.save()
        record(ctx, "cohort_invalidated", app, cohort_id=cohort.pk)


def reopen_locked(ctx, cohort):
    """Explicit staff revision, preserving old consent/answer and money history."""
    from apps.events import event_authority
    from .admission_answers import archive_locked
    from .admission_workflow import transition_registration_locked
    event_authority.require(ctx.actor, ctx.event, "review_applications")
    for app in cohort.applications.select_for_update().order_by("pk"):
        archive_locked(ctx, app)
        transition_registration_locked(application_id=app.pk, registration_id=app.registration_id,
            transition="reopen", actor=ctx.actor, reason_code="staff_cohort_reopen", locks=ctx.locks)
        app.state, app.cohort = "draft", None
        app.coc_revision = app.coc_accepted_at = app.answer_locked_at = None
        app.offered_at = app.rsvp_due_at = app.rsvp_accepted_at = None
        app.optional_consents, app.date_review_required = {}, True
        app.version += 1
        app.save()
        record(ctx, "application_cohort_reopened", app, cohort_id=cohort.pk, version=app.version)
    cohort.state, cohort.sealed_roster_hash, cohort.sealed_at = "draft", "", None
    cohort.version += 1
    cohort.save()
    record(ctx, "cohort_reopened", cohort, version=cohort.version)
