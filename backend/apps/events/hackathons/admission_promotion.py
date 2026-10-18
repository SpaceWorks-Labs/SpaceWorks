"""Automatic FIFO offers share the exact reviewed decision release service."""
from django.db import transaction
from django.db.models import Q
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework.exceptions import APIException
from apps.makerspaces.platform import feature_enabled
from .admission_decisions import release_decision_locked
from .admission_models import HackathonApplication, AdmissionWaitlistSweep
from .admission_transactions import record
from .capacity_admission import occupancy
from .review_models import ApplicationDecision, ApplicationDecisionBatch


def promote_locked(ctx, *, exclude_application_ids=(), limit=100, restart=True):
    if (not ctx.config.enabled or not feature_enabled(ctx.event.makerspace, "events.hackathons")
            or ctx.event.status != "published" or timezone.now() >= ctx.event.ends_at):
        return {"offered": 0, "skipped": []}
    cursor, _ = AdmissionWaitlistSweep.objects.get_or_create(event=ctx.event)
    rows = HackathonApplication.objects.filter(event=ctx.event, state="waitlisted").exclude(
        pk__in=exclude_application_ids).annotate(queue_at=Coalesce("queue_position_at", "submitted_at")).order_by("queue_at", "pk")
    if not restart and cursor.last_queue_at is not None:
        rows = rows.filter(Q(queue_at__gt=cursor.last_queue_at) | Q(queue_at=cursor.last_queue_at, pk__gt=cursor.last_application_id))
        if cursor.last_cohort_id is not None:
            rows = rows.exclude(cohort_id=cursor.last_cohort_id)
    limit = max(1, min(int(limit), 200))
    candidates = list(rows[:limit + 1])
    seen, skipped, offered = set(), [], 0
    for app in candidates[:limit]:
        key = ("cohort", app.cohort_id) if app.cohort_id else ("application", app.pk)
        if key in seen:
            continue
        seen.add(key)
        subject = app.cohort if app.cohort_id else app
        people = subject.applications.count() if app.cohort_id else 1
        available = occupancy(ctx.event, ctx.config)["offer_spots_left"]
        reason = None
        selector = {"cohort": subject} if app.cohort_id else {"application": subject}
        if ApplicationDecision.objects.filter(**selector, active_draft=True).exists():
            reason = "decision_already_staged"
        elif available is not None and people > available:
            reason = "group_does_not_fit"
        else:
            try:
                with transaction.atomic():
                    batch = ApplicationDecisionBatch.objects.create(event=ctx.event, actor=ctx.actor)
                    decision = ApplicationDecision.objects.create(batch=batch,
                        **({"cohort": subject} if app.cohort_id else {"application": subject}),
                        outcome="offer", reason_code="automatic_fifo", expected_subject_version=subject.version)
                    release_decision_locked(ctx, decision)
                    batch.state, batch.committed_at = "committed", timezone.now()
                    batch.save()
                    record(ctx, "waitlist_promoted", batch, people=people)
                    offered += people
            except APIException as exc:
                code = str(exc.detail.get("code", "")) if isinstance(exc.detail, dict) else ""
                if exc.status_code == 403:
                    reason = "no_longer_eligible"
                elif code in ("review_coverage_required", "roster_changed", "invalid_transition", "decision_already_staged", "event_date_changed", "capacity_full", "host_waiver_required", "admission_mapping_conflict"):
                    reason = code
                else:
                    raise
        if reason:
            skipped.append({"subject_kind": key[0], "subject_id": key[1], "people": people, "reason": reason})
            waiting = max(0, int((timezone.now() - (app.queue_position_at or app.submitted_at)).total_seconds()))
            record(ctx, "waitlist_group_skipped", app, people=people, reason_code=reason, waiting_seconds=waiting)
    if len(candidates) > limit:
        last = candidates[limit - 1]
        cursor.last_queue_at, cursor.last_application_id, cursor.last_cohort_id = last.queue_at, last.pk, last.cohort_id
    else:
        cursor.last_queue_at = cursor.last_application_id = cursor.last_cohort_id = None
    cursor.version += 1
    cursor.save()
    return {"offered": offered, "skipped": skipped, "has_more": len(candidates) > limit}
