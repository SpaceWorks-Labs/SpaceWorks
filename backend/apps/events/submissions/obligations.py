"""Permanent locator custody and leased, post-purge byte reconciliation."""
from apps.operations.cloud_jobs import bounded
from datetime import timedelta
import logging
from uuid import uuid4

from django.db import transaction
from django.utils import timezone

from apps.events.tasks_retention import require_retention_ready
from apps.makerspaces.models import Makerspace
from apps.makerspaces.storage_events_programme import provider_delta, settle
from apps.tenant_migration.gate_locks import shared_boundary
from .errors import SubmissionError
from .models_assets import EventAssetObligation, SubmissionAsset, HackathonParticipantAsset
from .storage_cleanup import delete_keys

logger = logging.getLogger(__name__)
MODELS = {model._meta.label: model for model in (SubmissionAsset, HackathonParticipantAsset)}


def reconcile(receipt_id, *, storage, now=None):
    now = now or timezone.now()
    original = EventAssetObligation.objects.get(pk=receipt_id)
    with shared_boundary(original.makerspace_id_snapshot):
        require_retention_ready(original.makerspace_id_snapshot)
        with transaction.atomic():
            row = EventAssetObligation.objects.select_for_update().get(pk=receipt_id)
            if row.next_attempt_at > now or row.lease_until and row.lease_until > now:
                return False
            # A surviving asset's workflow owns cleanup and usage release. This
            # deployment receipt may delete bytes only after its exact row is gone.
            model = MODELS[row.asset_label]
            if model.objects.filter(pk=row.asset_id_snapshot, public_id=row.asset_uuid).exists():
                row.next_attempt_at = now + timedelta(hours=6)
                row.save(update_fields=["next_attempt_at"])
                return False
            if row.write_not_after and row.write_not_after + timedelta(minutes=1) > now:
                row.next_attempt_at = row.write_not_after + timedelta(minutes=1)
                row.save(update_fields=["next_attempt_at"])
                return False
            token = uuid4()
            row.lease_token, row.lease_until = token, now + timedelta(minutes=5)
            row.attempts += 1
            row.save(update_fields=["lease_token", "lease_until", "attempts"])
        code = ""
        try:
            delete_keys(storage, [row.object_key, row.staging_key, row.verification_key])
        except SubmissionError:
            code = "storage_cleanup_pending"
        with transaction.atomic():
            # Tenant before child accounting. A purged tenant is expected absent.
            Makerspace.objects.select_for_update().filter(pk=row.makerspace_id_snapshot).first()
            row = EventAssetObligation.objects.select_for_update().get(pk=receipt_id)
            if row.lease_token != token or row.lease_until <= timezone.now():
                raise SubmissionError("lease_lost", 409)
            if not code:
                delta = settle(row, "release_all", row.reserved_bytes + row.charged_bytes)
                provider_delta(row, delta)
                row.last_cleaned_at = timezone.now()
            row.last_code, row.lease_token, row.lease_until = code, None, None
            row.next_attempt_at = timezone.now() + timedelta(hours=12 if code else 6)
            row.save()
        return not code


def sweep(*, storage, limit=100):
    now = timezone.now()
    from django.db.models import Q
    ids = EventAssetObligation.objects.filter(next_attempt_at__lte=now).filter(
        Q(lease_until__isnull=True) | Q(lease_until__lte=now)
    ).order_by("next_attempt_at", "pk").values_list("pk", flat=True)[:min(max(limit, 1), 500)]
    counts = {"cleaned": 0, "failed": 0}
    for pk in bounded.items(list(ids)):
        try:
            counts["cleaned"] += int(reconcile(pk, storage=storage))
        except Exception:
            counts["failed"] += 1
            logger.warning("event_asset_obligation_retry", extra={"receipt_id": pk})
    return counts
