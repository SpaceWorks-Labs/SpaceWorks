"""Private staging and atomic release; no participant reads of draft decisions."""
from datetime import timedelta
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .admission_errors import check_version, fail
from .admission_models import HackathonApplication, HackathonApplicationCohort
from .admission_transactions import command, notice, record
from .admission_workflow import transition_registration_locked
from .capacity_admission import occupancy, require_offer_room
from .review_models import ApplicationDecision, ApplicationDecisionBatch, ApplicationReviewAssignment


def subject_locked(event, selection):
    if selection.get("cohort_id"):
        subject = get_object_or_404(HackathonApplicationCohort.objects.select_for_update(), event=event, pk=selection["cohort_id"])
        applications = list(HackathonApplication.objects.select_for_update().filter(cohort=subject).order_by("pk"))
    else:
        subject = get_object_or_404(HackathonApplication.objects.select_for_update(), event=event, pk=selection["application_id"])
        if subject.cohort_id:
            fail("cohort_required", "Decide on the sealed team together.", status=400)
        applications = [subject]
    return subject, applications


def require_reviews(config, subject, decision):
    if config.review_mode == "auto" or decision.review_override_code:
        return
    key = "cohort_id" if isinstance(subject, HackathonApplicationCohort) else "application_id"
    source_at = subject.sealed_at if isinstance(subject, HackathonApplicationCohort) else subject.answers_changed_at
    if source_at is None:
        fail("review_coverage_required", "This subject needs a sealed review source.")
    from apps.events import event_authority
    from .review_workflow import conflicted
    assignments = ApplicationReviewAssignment.objects.filter(**{key: subject.pk}, assigned_at__gte=source_at,
        state="submitted", review__isnull=False, rubric_revision=config.review_rubric.get("revision", 1)).select_related("reviewer", "event")
    count = len({a.reviewer_id for a in assignments if event_authority.can(a.reviewer, a.event, "review_applications")
                 and not conflicted(a.event_id, a.reviewer_id, subject)})
    if count < config.review_count:
        fail("review_coverage_required", "This subject needs more distinct completed reviews.")


def release_decision_locked(ctx, decision, *, auto=False):
    subject, applications = subject_locked(ctx.event, {"application_id": decision.application_id, "cohort_id": decision.cohort_id})
    check_version(subject, decision.expected_subject_version)
    if not applications or any(a.state not in ("submitted", "waitlisted", "rejected") for a in applications):
        fail("invalid_transition", "This decision needs a submitted or queued application.")
    if ctx.config.team_mode == "team_together" and not decision.cohort_id:
        fail("cohort_required", "Seal the whole team before review.")
    if decision.cohort_id:
        from .admission_cohorts import require_sealed_roster
        require_sealed_roster(subject.team, list(subject.team.memberships.filter(state="active")))
    from .admission_answers import require_date_reviewed
    for app in applications:
        require_date_reviewed(app)
    require_reviews(ctx.config, subject, decision)
    now = timezone.now()
    if ctx.event.status != "published" or now >= ctx.event.ends_at:
        fail("applications_closed", "This event no longer accepts decisions.")
    state = {"offer": "offered", "waitlist": "waitlisted", "reject": "rejected"}[decision.outcome]
    if state == "offered":
        from .admission_transactions import require_member
        from apps.events.registration_access import require_registration_access
        for app in applications:
            require_member(app.member)
            require_registration_access(ctx.event, app.member)
        require_offer_room(ctx.event, ctx.config, len(applications))
    for app in applications:
        from .admission_answers import lock_answers_locked
        lock_answers_locked(ctx, app, at=now)
        old = app.state
        if state != "offered":
            transition_registration_locked(application_id=app.pk, registration_id=app.registration_id,
                transition="waitlist" if state == "waitlisted" else "reject",
                actor=ctx.actor, reason_code=decision.reason_code, locks=ctx.locks)
        else:
            transition_registration_locked(application_id=app.pk, registration_id=app.registration_id,
                transition="offer", actor=ctx.actor, reason_code=decision.reason_code, locks=ctx.locks)
            app.offered_at, app.rsvp_due_at = now, now + timedelta(days=ctx.config.rsvp_days)
            app.rsvp_accepted_at = None
        if state == "waitlisted":
            app.queue_position_at = now
        app.state, app.version = state, app.version + 1
        app.decision_revision += 1
        app.notified_decision = decision
        app.save()
        record(ctx, "decision_released", app, old_state=old, new_state=state,
               decision_id=decision.pk, revision=app.decision_revision,
               review_override_code=decision.review_override_code)
        notice(ctx, app, "application_" + state)
        if state == "rejected":
            from .team_lifecycle import eligibility_changed_locked
            eligibility_changed_locked(ctx, app)
    if isinstance(subject, HackathonApplicationCohort):
        subject.state, subject.version = state, subject.version + 1
        subject.save()
    decision.active_draft, decision.sent_at = False, now
    decision.sent_revision = max(a.decision_revision for a in applications)
    decision.save(update_fields=["active_draft", "sent_at", "sent_revision"])


def auto_release_locked(ctx, application):
    batch = ApplicationDecisionBatch.objects.create(event=ctx.event, actor=ctx.actor)
    left = occupancy(ctx.event, ctx.config)["offer_spots_left"]
    decision = ApplicationDecision.objects.create(batch=batch, application=application,
        outcome="offer" if left is None or left > 0 else "waitlist", reason_code="automatic_review",
        expected_subject_version=application.version)
    release_decision_locked(ctx, decision, auto=True)
    batch.state, batch.committed_at = "committed", timezone.now()
    batch.save()


def stage(*, event_id, actor, data):
    with command(event_id=event_id, actor=actor, data=data, action="decisions.stage", permission="review_applications") as ctx:
        if ctx.reference:
            return get_object_or_404(ApplicationDecisionBatch, pk=ctx.reference["id"], event=ctx.event)
        check_version(None, data["expected_version"])
        seen = set()
        batch = ApplicationDecisionBatch.objects.create(event=ctx.event, actor=actor)
        for item in data["decisions"]:
            subject, applications = subject_locked(ctx.event, item)
            check_version(subject, item["expected_version"])
            key = (type(subject).__name__, subject.pk)
            if key in seen:
                fail("duplicate_subject", "Choose each subject once.", status=400)
            seen.add(key)
            if not applications or any(a.state not in ("submitted", "waitlisted", "rejected") for a in applications):
                fail("invalid_transition", "This application cannot receive a staged decision.")
            selector = {"cohort": subject} if isinstance(subject, HackathonApplicationCohort) else {"application": subject}
            if ApplicationDecision.objects.filter(**selector, active_draft=True).exists():
                fail("decision_already_staged", "This subject already has a draft decision.")
            ApplicationDecision.objects.create(batch=batch, **selector, outcome=item["outcome"],
                reason_code=item["reason_code"], expected_subject_version=item["expected_version"],
                review_override_code=item.get("review_override_code", ""))
        record(ctx, "decisions_staged", batch, count=len(seen))
        ctx.finish("decision_batch", batch.pk, status=201)
        return batch


def finish_batch(*, event_id, actor, data, cancel=False):
    with command(event_id=event_id, actor=actor, data=data, action="decisions.cancel" if cancel else "decisions.release",
                 permission="review_applications") as ctx:
        batch = get_object_or_404(ApplicationDecisionBatch.objects.select_for_update(), event=ctx.event, pk=data["batch_id"])
        if ctx.reference:
            return batch
        check_version(batch, data["expected_version"])
        if batch.state != "draft":
            fail("invalid_transition", "This batch is no longer a draft.")
        decisions = list(batch.decisions.select_for_update().order_by("pk"))
        for decision in decisions:
            if cancel:
                decision.active_draft = False
                decision.save(update_fields=["active_draft"])
            else:
                release_decision_locked(ctx, decision)
        batch.state, batch.version = ("cancelled" if cancel else "committed"), batch.version + 1
        if not cancel:
            batch.committed_at = timezone.now()
        batch.save()
        record(ctx, "decisions_" + batch.state, batch, count=len(decisions), version=batch.version)
        ctx.finish("decision_batch", batch.pk)
        return batch
