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
    typed = adapter(snapshot.owner_kind)
    Owner = apps.get_model("makerspaces.Makerspace" if snapshot.owner_kind == "makerspace" else "organizations.Organization")
    with transaction.atomic():
        if snapshot.owner_kind == "makerspace" and Owner.objects.filter(pk=snapshot.owner_id).exists():
            assert_write_allowed(snapshot.owner_id)
        owner = Owner.objects.select_for_update().filter(pk=snapshot.owner_id).first()
        job = Cleanup.objects.select_for_update().get(pk=job_id)
        if job.completed_at or job.due_at > timezone.now():
            return False
        if typed.asset.objects.filter(object_key=job.object_key).exists():
            return False
        proven = job.object_key.startswith(prefix(job.owner_kind, job.owner_id, job.page_id))
        if not proven and job.owner_kind == "makerspace":
            from apps.tenant_migration.models_import_objects import TenantImportObject
            proven = TenantImportObject.objects.filter(target_key=job.object_key, bucket_kind="private",
                job__target_makerspace_id=job.owner_id, state__in=("promoted", "verified")).exists()
        if not proven:
            return False
        try:
            website_assets.delete_object("staging/" + job.object_key)
            website_assets.delete_object(job.object_key)
        except Exception:
            job.attempts += 1
            job.due_at = timezone.now() + timedelta(minutes=min(360, 5 * 2 ** min(job.attempts, 7)))
            job.save(update_fields=["attempts", "due_at"])
            logger.exception("public_page.object_cleanup_failed", extra={"cleanup_id": job.pk})
            return False
        if owner is not None:
            if job.owner_kind == "makerspace":
                limits.free_storage(owner, job.size_bytes)
            else:
                from apps.organizations.models_public_pages import OrganizationPublicPageStorage
                usage = OrganizationPublicPageStorage.objects.select_for_update().filter(organization=owner).first()
                if usage:
                    usage.used_bytes = max(0, usage.used_bytes - job.size_bytes)
                    usage.save(update_fields=["used_bytes"])
        job.completed_at = timezone.now()
        job.save(update_fields=["completed_at"])
        record(None, "public_page.asset_bytes_deleted", makerspace=owner if job.owner_kind == "makerspace" else None,
               target=None, meta={"owner_kind": job.owner_kind, "owner_id": job.owner_id, "cleanup_id": job.pk})
        return True


def sweep(*, limit=100):
    from .models_public_pages import MakerspacePublicPage
    from apps.organizations.models_public_pages import OrganizationPublicPage
    from apps.tenant_migration.gate_runtime import fanout_tenant_write
    counts = {"deleted": 0, "skipped": 0}
    for owner_id in MakerspacePublicPage.objects.values_list("makerspace_id", flat=True).iterator():
        with fanout_tenant_write(owner_id, operation="public_page_asset_cleanup", counts=counts) as allowed:
            if allowed:
                collect_unattached("makerspace", owner_id)
    for owner_id in OrganizationPublicPage.objects.values_list("organization_id", flat=True).iterator():
        collect_unattached("organization", owner_id)
    from .models_public_pages import MakerspacePublicPageAsset
    from apps.organizations.models_public_pages import OrganizationPublicPageAsset
    due = Cleanup.objects.filter(completed_at__isnull=True, due_at__lte=timezone.now()).exclude(
        object_key__in=MakerspacePublicPageAsset.objects.values("object_key")).exclude(
        object_key__in=OrganizationPublicPageAsset.objects.values("object_key"))
    for pk in due.order_by("id").values_list("pk", flat=True)[:limit]:
        job = Cleanup.objects.get(pk=pk)
        from .models import Makerspace
        if job.owner_kind == "makerspace" and Makerspace.objects.filter(pk=job.owner_id).exists():
            with fanout_tenant_write(job.owner_id, operation="public_page_asset_cleanup", counts=counts) as allowed:
                if allowed:
                    counts["deleted"] += int(clean_object(pk))
        else:
            counts["deleted"] += int(clean_object(pk))
    return counts
