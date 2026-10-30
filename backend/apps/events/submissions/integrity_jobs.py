"""GitHub first-commit flag job (G10, #8): information for judges, never a verdict.

For every hackathon in a space with `events.submission_integrity` on, each submission
snapshot taken after kickoff (submissions open, else the event start) is checked once:
its GitHub repository links are asked for a commit dated before kickoff. A hit records an
informational `SubmissionIntegrityFlag`; nothing else changes -- no state, no triage, no
eligibility, no visibility. GitHub failures fail safe: no flag, the attempt is logged and
retried up to three times an hour apart, then left `unavailable`.
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from apps.makerspaces.platform import feature_enabled
from apps.makerspaces.servability import servable_queryset
from apps.operations.cloud_jobs import bounded
from apps.separability.registry import runtime_active

logger = logging.getLogger(__name__)
FEATURE = "events.submission_integrity"
MAX_ATTEMPTS = 3
BATCH = 20


def kickoff(event):
    config = getattr(event, "hackathon_config", None)
    return (config.submission_opens_at if config and config.submission_opens_at else None) or event.starts_at


def enqueue_checks(space, now):
    from apps.events.models_r2_l2 import SubmissionIntegrityCheck
    from .models_projects import SubmissionSnapshot
    rows = (SubmissionSnapshot.objects.filter(submission__event__makerspace=space, integrity_check__isnull=True,
                                              submission__event__hackathon_config__enabled=True)
            .select_related("submission__event__hackathon_config").order_by("pk")[:200])
    created = 0
    for snapshot in rows:
        event = snapshot.submission.event
        if kickoff(event) > now:
            continue
        SubmissionIntegrityCheck.objects.get_or_create(snapshot=snapshot, defaults={
            "event": event, "makerspace": space, "next_attempt_at": now})
        created += 1
    return created


def _evidence(snapshot, event):
    from .integrity import check_github
    from .integrity_http import GitHubHttp
    links = list(snapshot.link_refs.filter(kind="repo", provider="github").order_by("pk")[:3])
    if not links:
        return "no_repository", None
    for link in links:
        evidence = check_github(repo_url=link.url, kickoff=kickoff(event), enabled=True, http=GitHubHttp())
        if evidence is not None:
            return "flagged", evidence
    return "clear", None


def run_check(check, now=None):
    """Network first, outside locks; then one short write under the event boundary."""
    from apps.events.services_write_boundary import write_boundary
    from apps.events.models_r2_l2 import SubmissionIntegrityCheck
    from .errors import SubmissionError
    from .integrity import record_flag_locked
    from .pii import prepare_documents
    now = now or timezone.now()
    snapshot, event = check.snapshot, check.event
    try:
        state, evidence = _evidence(snapshot, event)
    except SubmissionError as exc:
        logger.warning("submission_integrity_check_failed", extra={"check_id": check.pk, "code": str(exc)})
        state, evidence = "unavailable", None
    with prepare_documents(event.pk), write_boundary(event):
        row = SubmissionIntegrityCheck.objects.select_for_update().get(pk=check.pk)
        row.attempts += 1
        row.checked_at = now
        if state == "unavailable" and row.attempts < MAX_ATTEMPTS:
            row.state, row.next_attempt_at = "pending", now + timedelta(hours=1)
        else:
            row.state = state
        row.save(update_fields=["attempts", "checked_at", "state", "next_attempt_at"])
        if evidence is not None:
            record_flag_locked(actor=None, event=event, snapshot=snapshot, evidence=evidence)
    return row.state


def sweep_space(space, now=None):
    from apps.events.models_r2_l2 import SubmissionIntegrityCheck
    now = now or timezone.now()
    if not (feature_enabled(space, FEATURE) and feature_enabled(space, "events.hackathons")):
        return 0
    enqueue_checks(space, now)
    due = (SubmissionIntegrityCheck.objects.filter(makerspace=space, state="pending", next_attempt_at__lte=now)
           .select_related("snapshot", "event__hackathon_config", "event__makerspace").order_by("next_attempt_at", "pk")[:BATCH])
    done = 0
    for check in due:
        try:
            run_check(check, now)
            done += 1
        except Exception:
            logger.exception("submission_integrity_check_crashed", extra={"check_id": check.pk})
    return done


@shared_task
def sweep_integrity_checks_task():
    counts = {"checked": 0, "failed": 0, "skipped": 0}
    if not runtime_active("events"):
        return counts
    from apps.tenant_migration.gate_runtime import fanout_tenant_write
    spaces = servable_queryset().filter(enabled_modules__contains=["events"],
                                        enabled_features__contains=[FEATURE]).order_by("pk")
    for space in bounded.page(spaces, "event-integrity-spaces"):
        with fanout_tenant_write(space.pk, operation="event_submission_integrity", counts=counts) as allowed:
            if not allowed:
                continue
            try:
                counts["checked"] += sweep_space(space)
            except Exception:
                counts["failed"] += 1
                logger.exception("submission_integrity_sweep_failed", extra={"makerspace_id": space.pk})
    return counts
