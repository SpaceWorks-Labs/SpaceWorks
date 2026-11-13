"""Bounded stage recovery; canonical actions still enforce the clock on demand."""
import logging
from celery import shared_task
from django.db import transaction
from django.db.models import Value, BigIntegerField
from django.db.models.functions import Coalesce
from django.utils import timezone
from apps.events.models import Event, EventRegistration, HackathonApplication, EventSeries
from apps.events.contracts.providers import LockedContext
from apps.events.programme_locks import fences, lock_authority
from apps.makerspaces.guards import require_module_locked
from apps.makerspaces.servability import servable_q
from apps.events.tasks_sweeps import batch
from apps.operations.cloud_jobs import bounded
from apps.tenant_migration.gate_runtime import boundary_tenant_write
from .work_models import StageReconcileCursor, StageActivationJob
from .definition_models import EventStageForm
from .response_models import StageFormAssignment
from .trigger_service import resolve_participant
from . import stage_workflow

logger = logging.getLogger(__name__)


def reconcile_event(event_id, *, limit=100):
    seed = Event.objects.get(pk=event_id)
    cursor = StageReconcileCursor.objects.filter(event=seed).first()
    after = cursor.last_owner_id if cursor else 0
    owners = set(EventRegistration.objects.filter(event=seed, member_id__gt=after).order_by("member_id").values_list("member_id", flat=True).distinct()[:limit])
    owners.update(HackathonApplication.objects.filter(event=seed, member_id__gt=after).order_by("member_id").values_list("member_id", flat=True).distinct()[:limit])
    owners.update(StageFormAssignment.objects.filter(event=seed, owner_member_id__gt=after).order_by("owner_member_id").values_list("owner_member_id", flat=True).distinct()[:limit])
    normal_owners = tuple(sorted(owners)[:limit])
    owners = set(normal_owners)
    jobs = list(StageActivationJob.objects.filter(event=seed, state="pending").order_by("pk")[:1])
    for job in jobs:
        owners.update(job.participant_ids[job.cursor:job.cursor + limit])
    participant_owners = tuple(sorted(owners))
    owners.update(job.actor_id for job in jobs if job.actor_id)
    owners = tuple(sorted(owners))
    from .transactions import prepared_keys
    with boundary_tenant_write(seed.makerspace_id), prepared_keys(seed.makerspace_id), transaction.atomic(), fences(
        tenant_ids=(seed.makerspace_id,), account_ids=owners,
    ):
        if seed.series_id:
            EventSeries.objects.select_for_update().get(pk=seed.series_id)
        event = Event.objects.select_for_update().get(pk=seed.pk)
        event.makerspace = require_module_locked(event.makerspace_id, "events")
        cursor, _ = StageReconcileCursor.objects.get_or_create(event=event)
        cursor = StageReconcileCursor.objects.select_for_update().get(pk=cursor.pk)
        # Another worker advancing the page invalidates this predeclared owner set.
        if cursor.last_owner_id != after:
            return 0
        locks = LockedContext(event_id=event.pk, tenant_ids=(event.makerspace_id,), account_ids=owners)
        for job in jobs:
            if job.actor_id:
                lock_authority(job.actor, event)
        from .transactions import lock_stage_parents
        lock_stage_parents(event=event, owner_ids=participant_owners)
        definitions = list(EventStageForm.objects.select_for_update().filter(event=event, state="published").order_by("pk"))
        for owner_id in participant_owners:
            subject = resolve_participant(event=event, owner_id=owner_id)
            for definition in definitions:
                stage_workflow.activate_locked(definition=definition, subject=subject, locks=locks)
        for job in jobs:
            stage_workflow.process_activation_locked(job_id=job.pk, event=event, locks=locks, limit=limit)
        from .lifecycle import reschedule_event_locked
        reschedule_event_locked(event=event, locks=locks)
        stage_workflow.reconcile_deadlines_locked(event=event, now=timezone.now(), locks=locks)
        cursor.last_owner_id, cursor.version = (max(normal_owners) if normal_owners else 0), cursor.version + 1
        cursor.save()
        return len(owners)


@shared_task
def reconcile_stage_forms_task(limit=50):
    limit = batch(limit)
    from apps.makerspaces.scheduled_scope import live_space_ids
    events = Event.objects.filter(servable_q("makerspace"), makerspace_id__in=live_space_ids("events"),
        stage_forms__isnull=False).annotate(sweep=Coalesce("stage_reconcile_cursor__version", Value(0),
            output_field=BigIntegerField())).order_by("sweep", "pk").values_list("pk", flat=True).distinct()[:min(limit, 100)]
    processed = 0
    for event_id in bounded.items(list(events)):
        try:
            processed += reconcile_event(event_id)
        except Exception:
            logger.warning("stage_reconciliation_retry", extra={"event_id": event_id})
    return processed


@shared_task
def recover_stage_files_task(limit=50):
    from django.db.models import Q
    from .upload_models import StageFormAsset
    from .upload_jobs import validate_asset
    from apps.makerspaces.scheduled_scope import live_space_ids
    limit = batch(limit, heavy=True)
    now = timezone.now()
    rows = StageFormAsset.objects.filter(state__in=("uploaded", "validating"), expires_at__gt=now).filter(
        Q(lease_until__isnull=True) | Q(lease_until__lte=now)).filter(servable_q("event__makerspace"),
        event__makerspace_id__in=live_space_ids("events")).order_by("attempts", "pk").values_list("pk", flat=True)[:min(limit, 100)]
    count = 0
    for pk in bounded.items(list(rows)):
        try:
            validate_asset(pk)
            count += 1
        except Exception:
            logger.warning("stage_file_validation_retry", extra={"asset_id": pk})
    return count


@shared_task
def sweep_stage_file_retention_task(limit=100):
    from .retention import sweep
    return sweep(limit=batch(limit, heavy=True))
