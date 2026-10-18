"""Bounded stage recovery; canonical actions still enforce the clock on demand."""
import logging
from celery import shared_task
from django.db import transaction
from django.db.models import Value, BigIntegerField
from django.db.models.functions import Coalesce
from django.utils import timezone
from apps.encryption.tenant_preparation import prepare_tenant_key, tenant_key_context
from apps.events.models import Event, EventRegistration, HackathonApplication, EventSeries
from apps.events.contracts.providers import LockedContext
from apps.events.programme_locks import fences
from apps.makerspaces.guards import require_module_locked
from apps.makerspaces.servability import servable_q
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
    owners = tuple(sorted(owners))
    key = prepare_tenant_key(seed.makerspace_id)
    with boundary_tenant_write(seed.makerspace_id), tenant_key_context(key), transaction.atomic(), fences(
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
        definitions = list(EventStageForm.objects.select_for_update().filter(event=event, state="published").order_by("pk"))
        for owner_id in owners:
            subject = resolve_participant(event=event, owner_id=owner_id)
            for definition in definitions:
                stage_workflow.activate_locked(definition=definition, subject=subject, locks=locks)
        for job in jobs:
            stage_workflow.process_activation_locked(job_id=job.pk, event=event, locks=locks, limit=limit)
        stage_workflow.reconcile_deadlines_locked(event=event, now=timezone.now(), locks=locks)
        cursor.last_owner_id, cursor.version = (max(normal_owners) if normal_owners else 0), cursor.version + 1
        cursor.save()
        return len(owners)


@shared_task
def reconcile_stage_forms_task(limit=50):
    events = Event.objects.filter(servable_q("makerspace"), makerspace__enabled_modules__contains=["events"],
        stage_forms__isnull=False).annotate(sweep=Coalesce("stage_reconcile_cursor__version", Value(0),
            output_field=BigIntegerField())).order_by("sweep", "pk").values_list("pk", flat=True).distinct()[:min(limit, 100)]
    processed = 0
    for event_id in list(events):
        try:
            processed += reconcile_event(event_id)
        except Exception:
            logger.warning("stage_reconciliation_retry", extra={"event_id": event_id})
    return processed
