"""G schedules these bounded recoverable workers; HTTP never waits for storage."""
import logging

from celery import shared_task

from apps.operations.cloud_jobs import bounded
from django.utils import timezone

from .assets import validate_resume
from .exports import build_export
from .intents import apply_intent
from .lifecycle import expire_exports, expire_intents_and_receipts, run_object_cleanup
from .models import AccountSavedDetailsExportJob, MemberSavedAsset, SavedDetailUpdateIntent, SavedDetailsObjectCleanup
from .resume_retirement import retire_unreferenced_resumes

logger = logging.getLogger(__name__)


@shared_task
def process_saved_details():
    expire_exports()
    expire_intents_and_receipts()
    groups = (
        (SavedDetailUpdateIntent.objects.filter(state="pending").values_list("pk", flat=True)[:bounded.rows(100)], apply_intent),
        (MemberSavedAsset.objects.filter(state="validating").values_list("pk", flat=True)[:bounded.rows(25, heavy=True)],
         validate_resume),
        (AccountSavedDetailsExportJob.objects.filter(state__in=["queued", "building"]).values_list(
            "pk", flat=True)[:bounded.rows(10, heavy=True)], build_export),
        (MemberSavedAsset.objects.filter(next_cleanup_at__lte=timezone.now()).exclude(state__in=["deleting", "deleted"]).values_list("user_id", flat=True).distinct()[:bounded.rows(100, heavy=True)], retire_unreferenced_resumes),
        (SavedDetailsObjectCleanup.objects.filter(next_attempt_at__lte=timezone.now()).values_list(
            "pk", flat=True)[:bounded.rows(100, heavy=True)], run_object_cleanup),
    )
    for ids, run in groups:
        for pk in bounded.items(list(ids)):
            try:
                run(pk)
            except Exception:
                logger.warning("Saved details work requires retry", extra={"work_kind": run.__name__})
