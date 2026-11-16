"""How review stages meet staged decisions: `advance`, per-stage coverage and stale skips.

While stages are on for an event, every staged decision records the stage its application
stood in. At release, a decision whose application has since moved (another stage, a
new answer version, a decision already sent) is SKIPPED and recorded, never applied to
a subject that is no longer what the staffer reviewed. `advance` moves an application
to the next stage and leaves its registration and state untouched.
"""
from django.utils.translation import gettext
from django.utils import timezone

from apps.audit import services as audit
from apps.makerspaces.platform import feature_enabled

from .admission_errors import fail
from .admission_models import HackathonApplication, HackathonApplicationCohort
from .admission_stage_models import AdmissionStage, AdmissionStageEntry
from .admission_stages import STAGES, current_stage, enter_locked, materialize_entry_locked, next_stage

UNDECIDED = ("submitted", "waitlisted", "rejected")


def stages_active(event):
    return feature_enabled(event.makerspace, STAGES) and AdmissionStage.objects.filter(event=event).exists()


def stage_for_staging(event, subject, item):
    """The stage a new draft decision records; validates `advance`."""
    outcome = item["outcome"]
    if not stages_active(event):
        if outcome == "advance":
            fail("stages_not_configured", gettext("Add review stages before advancing applications."), status=400)
        return None
    if isinstance(subject, HackathonApplicationCohort):
        if outcome == "advance":
            fail("stages_individual_only", gettext("Review stages decide on individual applications."), status=400)
        return None
    stage = current_stage(subject)
    if outcome == "advance":
        if stage is None or item.get("stage_id") != stage.pk:
            fail("stage_mismatch", gettext("This application no longer stands in that stage."))
        if next_stage(stage) is None:
            fail("no_next_stage", gettext("This is the last stage; offer, waitlist or reject instead."), status=400)
    return stage


def required_stage(event, subject, decision):
    """The stage whose coverage gates this decision, or None for the single-round review."""
    if getattr(decision, "stage_id", None):
        return decision.stage
    if isinstance(subject, HackathonApplication) and stages_active(event):
        return current_stage(subject)
    return None


def require_stage_coverage(stage, subject, decision):
    from .admission_stage_review import coverage
    if decision.review_override_code:
        return
    if coverage(stage, subject) < stage.reviews_per_application:
        fail("review_coverage_required", gettext("This application needs more completed reviews in its stage."))


def _skip(ctx, decision, reason):
    decision.active_draft, decision.sent_at = False, timezone.now()
    decision.save(update_fields=["active_draft", "sent_at"])
    audit.record(ctx.actor, "event.application.decision_skipped", makerspace=ctx.event.makerspace, target=decision,
                 meta={"event_id": ctx.event.pk, "decision_id": decision.pk, "application_id": decision.application_id,
                       "stage_id": decision.stage_id, "reason_code": reason})


def release_stage_locked(ctx, decision):
    """True when this decision was handled here (skipped as stale, or an `advance`)."""
    if decision.stage_id is None:
        return False
    application = HackathonApplication.objects.select_for_update().get(pk=decision.application_id, event=ctx.event)
    stage = current_stage(application)
    if (application.state not in UNDECIDED or stage is None or stage.pk != decision.stage_id
            or application.version != decision.expected_subject_version):
        _skip(ctx, decision, "stale_decision")
        return True
    if decision.outcome != "advance":
        return False
    require_stage_coverage(stage, application, decision)
    following = next_stage(stage)
    if following is None:
        _skip(ctx, decision, "no_next_stage")
        return True
    materialize_entry_locked(ctx, application, stage)
    enter_locked(ctx, application, stage, kind=AdmissionStageEntry.Kind.ADVANCED, decision=decision,
                 reason_code=decision.reason_code)
    enter_locked(ctx, application, following, decision=decision, reason_code=decision.reason_code)
    application.version += 1
    application.save(update_fields=["version"])
    decision.active_draft, decision.sent_at = False, timezone.now()
    decision.save(update_fields=["active_draft", "sent_at"])
    audit.record(ctx.actor, "event.application.stage_advanced", makerspace=ctx.event.makerspace, target=application,
                 meta={"event_id": ctx.event.pk, "application_id": application.pk, "decision_id": decision.pk,
                       "from_stage_id": stage.pk, "stage_id": following.pk, "position": following.position})
    from .admission_webhooks import application_changed
    application_changed(ctx.event, application, "application_stage_advanced", stage=following)
    from apps.events.notices_r2_l21a import stage_advanced_notice
    stage_advanced_notice(ctx.event, application, following)
    return True
