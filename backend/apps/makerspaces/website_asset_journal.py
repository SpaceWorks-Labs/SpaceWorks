"""Independent event-object reservations, committed before storage work.

The FK-free journal survives reservation-pass rollback and process crashes.
Pending debt counts against quota; attachment and counter charge commit together.
"""

from datetime import timedelta
import psycopg2
from django.db import connections, router
from django.utils import timezone
from .models_page_cleanup import PublicPageObjectCleanup as Cleanup


def reserve(page, key, size, copies):
    """Persist quota debt under the venue lock, without charging the counter yet.

    The random final key is the write claim token. Cleanup increments attempts
    before deleting; finalize accepts only that exact, unclaimed live receipt.
    This is the evidence finalizer's claim/work/complete fence without a new model.
    """
    from django.db import transaction
    from . import limits
    from .website_assets import prefix
    private = key.startswith(prefix("events", page.makerspace_id, page.pk))
    cover = key.startswith(f"event/{page.makerspace_id}/")
    if not (private or cover):
        raise ValueError("Only fresh event keys may be reserved.")
    # Reuse the limit policy, but leave the counter unchanged. Independently
    # committed unaccounted intents are the reservation until domain finalize.
    with transaction.atomic():
        limits.add_storage(page.makerspace, size)
        transaction.set_rollback(True)
    alias = router.db_for_write(Cleanup)
    source = connections[alias]
    # Like the source-gate lock connection, this autonomous transaction must
    # bypass Django's alias lifecycle and survive the domain pass's rollback.
    # It only inserts FK-free debt: the tentative page/event may be uncommitted
    # on the caller's connection, so never read domain rows through this one.
    isolated = psycopg2.connect(**source.get_connection_params())
    now = timezone.now()
    try:
        isolated.autocommit = True
        table = source.ops.quote_name(Cleanup._meta.db_table)
        with isolated.cursor() as cursor:
            cursor.execute(f"""INSERT INTO {table}
                (owner_kind, owner_id, page_id, object_key, size_bytes, storage_accounted, ownership_proven,
                 due_at, attempts, created_at) VALUES (%s,%s,%s,%s,%s,false,true,%s,0,%s) RETURNING id""",
                ["event", page.makerspace_id, page.pk, key, size, now + timedelta(hours=1), now])
            job_id = cursor.fetchone()[0]
    finally:
        isolated.close()
    copies.journal_ids.append(job_id)
    copies.journal_keys.add(key)
    return job_id


def finalize(plan):
    """Attach a verified claim and charge once, in the domain commit transaction."""
    from . import limits
    from .public_page_asset_cleanup import _event_cover
    from rest_framework.exceptions import ValidationError
    job = Cleanup.objects.select_for_update().get(pk=plan["job_id"])
    if (not plan["ready"] or job.object_key != plan["key"] or job.attempts
            or job.owner_kind != "event" or job.owner_id != plan["page"].makerspace_id
            or job.page_id != plan["page"].pk):
        raise ValidationError({"revision": "The image reservation expired. Retry the operation."})
    if job.storage_accounted or (_event_cover(job) and job.completed_at):
        return
    if job.completed_at or job.due_at <= timezone.now():
        raise ValidationError({"revision": "The image reservation expired. Retry the operation."})
    # Remove this debt before add_storage includes all OTHER reservations. Both
    # this flag and the actual charge roll back if any graph finalization fails.
    job.storage_accounted = True
    job.save(update_fields=["storage_accounted"])
    limits.add_storage(plan["page"].makerspace, job.size_bytes)
    if _event_cover(job):
        # The legacy public-image lifecycle owns quota release after attachment.
        # Keep a late-write repair receipt, but never credit that counter again.
        job.storage_accounted = False
        job.completed_at = timezone.now()
        job.save(update_fields=["storage_accounted", "completed_at"])


def pending_bytes(makerspace_id):
    from django.db.models import Sum
    return Cleanup.objects.filter(owner_kind="event", owner_id=makerspace_id,
        storage_accounted=False, completed_at__isnull=True).aggregate(total=Sum("size_bytes"))["total"] or 0


def pending_count(page, *, exclude_ids=()):
    return Cleanup.objects.filter(owner_kind="event", owner_id=page.makerspace_id, page_id=page.pk,
        completed_at__isnull=True).exclude(object_key__startswith=f"event/{page.makerspace_id}/").exclude(
            pk__in=exclude_ids).exclude(
            object_key__in=page.assets.values("object_key")).count()


def accounted_pending_bytes(makerspace_id):
    from django.db.models import Sum
    from django.apps import apps
    from .models_public_pages import MakerspacePublicPageAsset
    jobs = Cleanup.objects.filter(owner_kind__in=("event", "makerspace"), owner_id=makerspace_id,
        storage_accounted=True, completed_at__isnull=True).exclude(
            object_key__in=MakerspacePublicPageAsset.objects.values("object_key"))
    if apps.is_installed("apps.events"):
        jobs = jobs.exclude(object_key__in=apps.get_model("events.EventPageAsset").objects.values("object_key"))
        jobs = jobs.exclude(object_key__in=apps.get_model("events.Event").objects.values("image_key"))
    return jobs.aggregate(total=Sum("size_bytes"))["total"] or 0


def schedule(asset):
    from .website_assets import owns
    from rest_framework.exceptions import ValidationError
    if not owns(asset.object_key, "events", asset.page.makerspace_id, asset.page_id, asset=asset):
        raise ValidationError("Image is not owned by this event page.")
    job, _ = Cleanup.objects.update_or_create(object_key=asset.object_key, defaults={
        "owner_kind": "event", "owner_id": asset.page.makerspace_id, "page_id": asset.page_id,
        "size_bytes": asset.size_bytes, "storage_accounted": True, "ownership_proven": True,
        "due_at": timezone.now(), "completed_at": None})
    return job.pk
