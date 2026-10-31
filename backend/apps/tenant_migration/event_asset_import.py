"""Target-owned event asset byte proofs and separate provider accounting."""
from django.apps import apps
from django.conf import settings
from django.db import transaction
from django.db.models import F, Q

from apps.makerspaces import limits
from apps.makerspaces.models import Makerspace
from apps.backup.capture_managers import every_row


ASSET_LABELS = ("events.SubmissionAsset", "events.HackathonParticipantAsset")


def canonical_asset(*, tenant_id, key, size, digest=None, bucket_kind="private"):
    if bucket_kind != "private":
        return False
    for label in ASSET_LABELS:
        model = apps.get_model(label)
        rows = every_row(model).filter(event__makerspace_id=tenant_id, object_key=key,
                                    actual_bytes=size, state="ready")
        if digest is not None:
            rows = rows.filter(sha256=digest)
        if rows.exists():
            return True
    return False


def charge_bytes(makerspace, size, *, key, digest=None, bucket_kind="private"):
    if canonical_asset(tenant_id=makerspace.pk, key=key, size=size, digest=digest, bucket_kind=bucket_kind):
        if not limits.is_self_host():
            Makerspace.objects.filter(pk=makerspace.pk).update(storage_bytes_used=F("storage_bytes_used") + size)
    else:
        limits.add_storage(makerspace, size)


def publish_assets(tenant_id, accepted_objects):
    """Called only inside the target publication transaction after byte verification."""
    from apps.events.models import Event, EventSeries
    from apps.events.submissions.portability import finalize_imported_assets
    events = Event.objects.filter(makerspace_id=tenant_id)
    series = events.exclude(series_id=None).values_list("series_id", flat=True)
    list(EventSeries.objects.select_for_update().filter(pk__in=series).order_by("pk"))
    locked = list(events.select_for_update().order_by("pk"))
    space = Makerspace.objects.select_for_update().get(pk=tenant_id)
    if space.lifecycle_state != "importing":
        raise ValueError("Event asset publication requires the target import state.")
    for event in locked:
        event.makerspace = space
        # Ordinary events need no new usage row or target event storage allowance.
        if any(every_row(apps.get_model(label)).filter(event=event).exists() for label in ASSET_LABELS):
            finalize_imported_assets(event=event, accepted_objects=accepted_objects)


def publish_portable(job):
    from .models_import_objects import TenantImportObject
    proofs = {row.target_key: (row.size, row.sha256, "") for row in job.import_objects.filter(
        state=TenantImportObject.State.VERIFIED, bucket_kind="private")}
    publish_assets(job.target_makerspace_id, proofs)


def publish_raw(*, makerspace, ledger):
    proofs = {}
    done = {(row["phase"], row["attempt"]) for row in ledger.records() if row["state"] == "done"}
    for row in ledger.records():
        if row["phase"].startswith("object-load-") and (row["phase"], row["attempt"]) in done:
            detail = row["detail"]
            if detail.get("accepted_size") is not None and detail.get("bucket") == settings.AWS_STORAGE_BUCKET_NAME:
                proofs[detail["key"]] = (detail["accepted_size"], detail["digest"], "")
    with transaction.atomic():
        publish_assets(makerspace.pk, proofs)
