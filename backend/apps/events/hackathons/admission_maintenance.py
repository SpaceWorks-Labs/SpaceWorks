"""Scheduled expiry and FIFO promotion; G registers source-gated task entry points."""
from contextlib import ExitStack, contextmanager
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from apps.events.contracts.providers import LockedContext
from apps.events.models import Event
from apps.tenant_migration.gate_runtime import boundary_tenant_write
from .admission_models import HackathonApplication, HackathonConfig
from .admission_ports import ports
from .admission_transactions import CommandContext, lock_domain_parents, record
from .capacity_admission import occupancy


@contextmanager
def maintenance_boundary(event_id):
    """Internal task only. No client flag or actor can request this authority."""
    integration = ports()
    event = get_object_or_404(Event, pk=event_id)
    tenants, accounts = integration.event_scopes(event_id=event_id, account_ids=())
    tenants, accounts = tuple(sorted(set(tenants))), tuple(sorted(set(accounts)))
    integration.assert_encryption_ready(event_id=event_id)
    with ExitStack() as stack:
        for tenant_id in tenants:
            stack.enter_context(boundary_tenant_write(tenant_id))
        stack.enter_context(transaction.atomic())
        stack.enter_context(integration.fences(tenant_ids=tenants, account_ids=accounts))
        event = integration.lock_event(event_id=event_id, account_ids=accounts)
        config = get_object_or_404(HackathonConfig.objects.select_for_update(), event=event)
        lock_domain_parents(event_id)
        yield CommandContext(event, config, None,
            LockedContext(event_id=event_id, tenant_ids=tenants, account_ids=accounts), None, None)


def expire_due(*, event_id, limit=100):
    """Idempotent by current state/deadline; bounded batches, no external I/O."""
    from .admission_rsvp import subject_applications_locked, end_group_locked
    expired = 0
    with maintenance_boundary(event_id) as ctx:
        due = list(HackathonApplication.objects.filter(event=ctx.event, state="offered",
            rsvp_due_at__lte=timezone.now()).order_by("rsvp_due_at", "pk")[:limit])
        handled = set()
        for app in due:
            if app.pk in handled:
                continue
            cohort, applications = subject_applications_locked(app)
            if not cohort:
                app = HackathonApplication.objects.select_for_update().get(pk=app.pk)
                applications = [app]
            if any(a.state != "offered" for a in applications):
                continue
            end_group_locked(ctx, applications, "expired", reason_code="rsvp_deadline")
            handled.update(a.pk for a in applications)
            expired += len(applications)
            if cohort:
                cohort.state, cohort.version = "expired", cohort.version + 1
                cohort.save()
        from .admission_promotion import promote_locked
        promote_locked(ctx)
    return expired


def promotion_preview(*, event, config):
    from .capacity_admission import preview
    groups, seen = [], set()
    for app in HackathonApplication.objects.filter(event=event, state="waitlisted").order_by("queue_position_at", "pk"):
        key = ("cohort", app.cohort_id) if app.cohort_id else ("application", app.pk)
        if key in seen:
            continue
        seen.add(key)
        count = app.cohort.applications.count() if app.cohort_id else 1
        groups.append((key, count))
    return preview(event, config, groups)


def promote_waiters(*, event_id, actor, data):
    """Staff explicit FIFO release uses the same decision service and N reviews."""
    from .admission_transactions import command
    from .admission_decisions import release_decision_locked
    from .review_models import ApplicationDecision, ApplicationDecisionBatch
    from .admission_errors import check_version
    with command(event_id=event_id, actor=actor, data=data, action="waitlist.promote", permission="review_applications") as ctx:
        if ctx.reference:
            return get_object_or_404(ApplicationDecisionBatch, pk=ctx.reference["id"], event=ctx.event)
        check_version(ctx.config, data["expected_version"])
        selection = promotion_preview(event=ctx.event, config=ctx.config)
        batch = ApplicationDecisionBatch.objects.create(event=ctx.event, actor=actor)
        for kind, pk in selection["selected"]:
            from .admission_models import HackathonApplicationCohort
            model = HackathonApplicationCohort if kind == "cohort" else HackathonApplication
            subject = model.objects.get(pk=pk, event=ctx.event)
            selector = {"cohort": subject} if kind == "cohort" else {"application": subject}
            decision = ApplicationDecision.objects.create(batch=batch, **selector, outcome="offer",
                expected_subject_version=subject.version, reason_code="waitlist_fifo")
            release_decision_locked(ctx, decision)
        batch.state, batch.committed_at = "committed", timezone.now()
        batch.save()
        record(ctx, "waitlist_promoted", batch, count=len(selection["selected"]), skipped=len(selection["skipped"]))
        ctx.finish("decision_batch", batch.pk)
        return batch


def resume_waitlist(*, event_id):
    """G's periodic sweep resumes the persisted cursor after queue/task loss."""
    from .admission_promotion import promote_locked
    with maintenance_boundary(event_id) as ctx:
        return promote_locked(ctx, restart=False)


def freeze_closed_applications(*, event_id, limit=100):
    """Lock the as-of date at application close without approving or clearing review."""
    from .admission_answers import lock_answers_locked
    with maintenance_boundary(event_id) as ctx:
        if not ctx.config.application_closes_at or timezone.now() < ctx.config.application_closes_at:
            return 0
        applications = list(HackathonApplication.objects.select_for_update().filter(event=ctx.event,
            state="submitted", answer_locked_at__isnull=True).order_by("pk")[:max(1, min(limit, 200))])
        for app in applications:
            lock_answers_locked(ctx, app)
            app.version += 1
            app.save(update_fields=["version"])
        return len(applications)
