"""Independent cleanup intent for private event copies inside a clone transaction.

The journal deliberately has no owner FKs. Its autocommit connection can persist
intent without waiting on the caller's uncommitted page or tenant row. The caller
charges quota first under the tenant lock, then marks the journal accounted in its
own transaction. Rollback leaves an unaccounted debt, counted by storage limits.
"""

from datetime import timedelta
from django.db import connections, router
from django.utils import timezone
from .models_page_cleanup import PublicPageObjectCleanup as Cleanup


def enlist(page, key, size, copies):
    from .website_assets import prefix
    if not key.startswith(prefix("events", page.makerspace_id, page.pk)):
        raise ValueError("Cleanup intent requires a freshly owned event key.")
    alias = router.db_for_write(Cleanup)
    isolated = connections[alias].copy(alias="website_cleanup_intent")
    now = timezone.now()
    try:
        isolated.ensure_connection()
        isolated.set_autocommit(True)
        table = isolated.ops.quote_name(Cleanup._meta.db_table)
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
    # This update commits with the asset/quota rows, or rolls back with them.
    Cleanup.objects.using(alias).filter(pk=job_id).update(storage_accounted=True)
    return job_id


def pending_bytes(makerspace_id):
    from django.db.models import Sum
    return Cleanup.objects.filter(owner_kind="event", owner_id=makerspace_id,
        storage_accounted=False, completed_at__isnull=True).aggregate(total=Sum("size_bytes"))["total"] or 0


def pending_count(page):
    return Cleanup.objects.filter(owner_kind="event", owner_id=page.makerspace_id, page_id=page.pk,
        completed_at__isnull=True).exclude(object_key__in=page.assets.values("object_key")).count()


def accounted_pending_bytes(makerspace_id):
    from django.db.models import Sum
    from django.apps import apps
    from .models_public_pages import MakerspacePublicPageAsset
    jobs = Cleanup.objects.filter(owner_kind__in=("event", "makerspace"), owner_id=makerspace_id,
        storage_accounted=True, completed_at__isnull=True).exclude(
            object_key__in=MakerspacePublicPageAsset.objects.values("object_key"))
    if apps.is_installed("apps.events"):
        jobs = jobs.exclude(object_key__in=apps.get_model("events.EventPageAsset").objects.values("object_key"))
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
