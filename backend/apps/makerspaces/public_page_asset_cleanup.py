"""Retryable byte deletion; quota is freed only after both keys are confirmed gone."""

import logging
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from apps.audit.services import record
from .models_page_cleanup import PublicPageObjectCleanup as Cleanup
from .public_page_adapters import adapter
from .public_page_assets import prefix, owns
from . import website_assets, limits

logger = logging.getLogger(__name__)
# A completed event receipt is repaired (re-deleted) only long enough to outlast a
# timed-out PUT/COPY that lands late. Past this window it is inert history.
REPAIR_WINDOW = timedelta(hours=24)


def collect_unattached(kind, owner_id):
    from django.apps import apps
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    typed = adapter(kind)
    Owner = apps.get_model("makerspaces.Makerspace" if kind == "makerspace" else "organizations.Organization")
    with transaction.atomic():
        if kind == "makerspace":
            assert_write_allowed(owner_id)
        owner = Owner.objects.select_for_update().filter(pk=owner_id).first()
        if owner is None:
            return 0
        page = typed.page.objects.select_for_update().filter(**typed.lookup(owner)).first()
        if page is None:
            return 0
        removed = 0
        for asset in page.assets.filter(created_at__lte=timezone.now() - timedelta(hours=24)).order_by("id")[:50]:
            if typed.asset_reference.objects.filter(asset=asset).exists() or not owns(asset, kind, owner_id):
                continue
            Cleanup.objects.update_or_create(object_key=asset.object_key, defaults={"owner_kind": kind,
                "owner_id": owner_id, "page_id": page.pk, "size_bytes": asset.size_bytes,
                "due_at": timezone.now(), "completed_at": None})
            asset.delete()
            removed += 1
        if removed:
            page.version += 1
            page.save(update_fields=["version"])
            record(None, "public_page.unattached_assets_removed", makerspace=owner if kind == "makerspace" else None,
                   target=page, meta={"owner_kind": kind, "owner_id": owner_id, "count": removed})
        return removed


def clean_object(job_id):
    from django.apps import apps
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    snapshot = Cleanup.objects.get(pk=job_id)
    tenant = snapshot.owner_kind in {"makerspace", "event"}
    Owner = apps.get_model("makerspaces.Makerspace" if tenant else "organizations.Organization")
    with transaction.atomic():
        if tenant and Owner.objects.filter(pk=snapshot.owner_id).exists():
            assert_write_allowed(snapshot.owner_id)
        owner = Owner.objects.select_for_update().filter(pk=snapshot.owner_id).first()
        job = Cleanup.objects.select_for_update().get(pk=job_id)
        if job.due_at > timezone.now() or (job.completed_at and (
                job.owner_kind != "event" or job.completed_at < timezone.now() - REPAIR_WINDOW)):
            return False
        if tenant and owner is None and not _tenant_purged(job.owner_id):
            # A tenant absent from a restored readable main may still arrive by slice
            # merge; only an audited whole-tenant purge proves its bytes are garbage.
            return False
        if _has_asset(job):
            return False
        expected = (website_assets.prefix("events", job.owner_id, job.page_id) if job.owner_kind == "event"
                    else prefix(job.owner_kind, job.owner_id, job.page_id))
        proven = job.object_key.startswith(expected) or (job.owner_kind == "event" and job.ownership_proven)
        if job.owner_kind == "makerspace":
            proven = proven or job.object_key.startswith(f"events/website/{job.owner_id}/{job.page_id}/")
            # Whole-tenant deletion removes its import journals too. This exact-key
            # intent was validated and committed before that graph was removed.
            if owner is None:
                from apps.inventory.public_image_storage import is_safe_object_key
                proven = is_safe_object_key(job.object_key)
        if not proven and tenant:
            from apps.tenant_migration.models_import_objects import TenantImportObject
            proven = TenantImportObject.objects.filter(target_key=job.object_key, bucket_kind="private",
                job__target_makerspace_id=job.owner_id, state__in=("promoted", "verified")).exists()
        if not proven:
            return False
        # Claim before network I/O. Upload finalizers refuse a claimed journal,
        # so a stalled writer cannot attach bytes after cleanup has started.
        job.attempts += 1
        job.due_at = timezone.now() + timedelta(minutes=min(360, 5 * 2 ** min(job.attempts, 7)))
        job.save(update_fields=["attempts", "due_at"])
    from apps.inventory import public_image_storage
    storage = public_image_storage if _event_cover(job) else website_assets
    try:
        if not _event_cover(job) and storage.delete_object("staging/" + job.object_key) is not True:
            raise RuntimeError("Staging deletion was not confirmed.")
        if storage.delete_object(job.object_key) is not True:
            raise RuntimeError("Final deletion was not confirmed.")
    except Exception:
        logger.exception("public_page.object_cleanup_failed", extra={"cleanup_id": job.pk})
        return False
    with transaction.atomic():
        if tenant and Owner.objects.filter(pk=snapshot.owner_id).exists():
            assert_write_allowed(snapshot.owner_id)
        owner = Owner.objects.select_for_update().filter(pk=snapshot.owner_id).first()
        job = Cleanup.objects.select_for_update().get(pk=job_id)
        if job.completed_at:
            # A timed-out PUT/COPY can finish late. Keep repairing event keys,
            # without releasing quota or writing a deletion audit twice.
            job.due_at = timezone.now() + timedelta(hours=6)
            job.save(update_fields=["due_at"])
            return False
        if owner is not None and job.storage_accounted:
            if tenant:
                limits.free_storage(owner, job.size_bytes)
            else:
                from apps.organizations.models_public_pages import OrganizationPublicPageStorage
                usage = OrganizationPublicPageStorage.objects.select_for_update().filter(organization=owner).first()
                if usage:
                    usage.used_bytes = max(0, usage.used_bytes - job.size_bytes)
                    usage.save(update_fields=["used_bytes"])
        job.completed_at = timezone.now()
        if job.owner_kind == "event":
            job.due_at = timezone.now() + timedelta(hours=6)
        job.save(update_fields=["completed_at", "due_at"])
        record(None, "public_page.asset_bytes_deleted", makerspace=owner if tenant else None,
               target=None, meta={"owner_kind": job.owner_kind, "owner_id": job.owner_id, "cleanup_id": job.pk})
        return True


def _tenant_purged(makerspace_id):
    from apps.audit.models import AuditLog
    return AuditLog.objects.filter(action="makerspace.purge_started",
                                   meta__makerspace_id=makerspace_id).exists()


def _has_asset(job):
    from django.apps import apps
    from .models_public_pages import MakerspacePublicPageAsset
    from apps.organizations.models_public_pages import OrganizationPublicPageAsset
    # Cleanup keys can outlive their typed owner; check every live asset family.
    if (MakerspacePublicPageAsset.objects.filter(object_key=job.object_key).exists()
            or OrganizationPublicPageAsset.objects.filter(object_key=job.object_key).exists()):
        return True
    if not apps.is_installed("apps.events"):
        return False
    if apps.get_model("events.EventPageAsset").objects.filter(object_key=job.object_key).exists():
        return True
    return (apps.get_model("events.Event").objects.filter(image_key=job.object_key).exists()
            or apps.get_model("events.EventSeries").objects.filter(image_key=job.object_key).exists())


def _event_cover(job):
    return job.owner_kind == "event" and job.object_key.startswith(f"event/{job.owner_id}/")


def sweep(*, limit=100):
    from .models_public_pages import MakerspacePublicPage
    from apps.organizations.models_public_pages import OrganizationPublicPage
    from apps.tenant_migration.gate_runtime import fanout_tenant_write
    counts = {"deleted": 0, "skipped": 0}
    for owner_id in MakerspacePublicPage.objects.values_list("makerspace_id", flat=True).iterator():
        with fanout_tenant_write(owner_id, operation="public_page_asset_cleanup", counts=counts) as allowed:
            if not allowed:
                continue
            collect_unattached("makerspace", owner_id)
    for owner_id in OrganizationPublicPage.objects.values_list("organization_id", flat=True).iterator():
        collect_unattached("organization", owner_id)
    from apps.separability.registry import runtime_active
    from django.apps import apps
    if apps.is_installed("apps.events") and runtime_active("events"):
        from apps.events.website_asset_cleanup import collect_unattached as collect_events
        from apps.events.models_website import EventPage
        for page_id, owner_id in EventPage.objects.values_list("pk", "makerspace_id").iterator():
            with fanout_tenant_write(owner_id, operation="public_page_asset_cleanup", counts=counts) as allowed:
                if not allowed:
                    continue
                collect_events(page_id)
    from .models_public_pages import MakerspacePublicPageAsset
    from apps.organizations.models_public_pages import OrganizationPublicPageAsset
    from django.db.models import F, Q
    now = timezone.now()
    due = Cleanup.objects.filter(Q(completed_at__isnull=True) | Q(
        owner_kind="event", completed_at__gte=now - REPAIR_WINDOW), due_at__lte=now).exclude(
        object_key__in=MakerspacePublicPageAsset.objects.values("object_key")).exclude(
        object_key__in=OrganizationPublicPageAsset.objects.values("object_key"))
    if apps.is_installed("apps.events"):
        due = due.exclude(object_key__in=apps.get_model("events.EventPageAsset").objects.values("object_key"))
        for model in ("events.Event", "events.EventSeries"):
            due = due.exclude(object_key__in=apps.get_model(model).objects.exclude(
                image_key__isnull=True).values("image_key"))
    # Pending deletions (and their quota refunds) go before repair passes.
    ordered = due.order_by(F("completed_at").asc(nulls_first=True), "due_at", "id")
    for pk in ordered.values_list("pk", flat=True)[:limit]:
        job = Cleanup.objects.get(pk=pk)
        from .models import Makerspace
        if job.owner_kind in {"makerspace", "event"} and Makerspace.objects.filter(pk=job.owner_id).exists():
            with fanout_tenant_write(job.owner_id, operation="public_page_asset_cleanup", counts=counts) as allowed:
                if not allowed:
                    continue
                counts["deleted"] += int(clean_object(pk))
        else:
            counts["deleted"] += int(clean_object(pk))
    return counts
