"""Private typed assets. Durable intent commits before any external byte write."""

from django.utils.translation import gettext
from datetime import timedelta
from uuid import uuid4
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from . import website_assets, limits
from .models_page_cleanup import PublicPageObjectCleanup as Cleanup
from .public_page_services import lock_state, ensure_page, finish, editor_state
from .public_page_errors import PageConflict

ORGANIZATION_STORAGE_BYTES = 100_000_000
MAX_ASSETS = 50


def prefix(kind, owner_id, page_id):
    if kind not in {"makerspace", "organization"}:
        raise ValueError("Typed page owner required.")
    return f"pages/{'makerspaces' if kind == 'makerspace' else 'organizations'}/{int(owner_id)}/{int(page_id)}/"


def charge_storage(kind, owner, size):
    if kind == "makerspace":
        limits.add_storage(owner, size)
        return
    from apps.organizations.models_public_pages import OrganizationPublicPageStorage as Storage
    usage, _ = Storage.objects.get_or_create(organization=owner)
    usage = Storage.objects.select_for_update().get(pk=usage.pk)
    if usage.used_bytes + size > ORGANIZATION_STORAGE_BYTES:
        raise ValidationError({"file": gettext("This organization's 100 MB page storage allowance is full.")})
    usage.used_bytes += size
    usage.save(update_fields=["used_bytes"])


def upload(kind, owner_id, *, actor, version, file, alt_text):
    if not isinstance(alt_text, str) or not alt_text.strip() or len(alt_text) > 200:
        raise ValidationError({"alt_text": gettext("Provide an image description of at most 200 characters.")})
    # Refuse unauthorized callers before reading or decoding any bytes; the locked
    # reservation below still rechecks authority and the tenant write fence.
    from .public_page_adapters import adapter
    adapter(kind).read_owner(owner_id, actor)
    raw = file.read(website_assets.MAX_BYTES + 1)
    if len(raw) > website_assets.MAX_BYTES:
        from .public_page_errors import PagePayloadTooLarge
        raise PagePayloadTooLarge()
    converted = website_assets.webp(raw)
    # Independent durable reservation survives storage errors and process death.
    with transaction.atomic(durable=True):
        typed, owner, actor, page = lock_state(kind, owner_id, actor, version)
        page = ensure_page(typed, owner, page, actor)
        pending = Cleanup.objects.filter(owner_kind=kind, owner_id=owner_id, completed_at__isnull=True).exclude(
            object_key__in=page.assets.values("object_key"))
        if kind == "makerspace":
            from .public_page_lifecycle import event_cleanup_keys
            pending = pending.exclude(event_cleanup_keys())
        if kind == "makerspace":
            from apps.managed_hosting.extra_quotas import check_extra_quota
            check_extra_quota(owner, "public_page_assets")  # decision 328a: refuses only a NEW image
        if page.assets.count() + pending.count() >= MAX_ASSETS:
            raise ValidationError({"file": gettext("A page may retain at most 50 assets, including pending uploads.")})
        charge_storage(kind, owner, len(converted))
        key = prefix(kind, owner_id, page.pk) + uuid4().hex + ".webp"
        job = Cleanup.objects.create(owner_kind=kind, owner_id=owner_id, page_id=page.pk, object_key=key,
                                     size_bytes=len(converted), due_at=timezone.now() + timedelta(hours=1))
        finish(typed, owner, page, actor, "public_page.asset_reserved")
        reserved_version = page.version
        job_id = job.pk
    try:
        website_assets._put("staging/" + key, raw, "application/octet-stream")
        website_assets._put(key, converted, "image/webp")
        website_assets.delete_object("staging/" + key)
        with transaction.atomic(durable=True):
            typed, owner, actor, page = lock_state(kind, owner_id, actor, reserved_version)
            job = Cleanup.objects.select_for_update().filter(pk=job_id, completed_at__isnull=True, attempts=0).first()
            if job is None:
                raise PageConflict("stale_version", gettext("The upload expired. Upload the image again."))
            asset = typed.asset.objects.create(page=page, object_key=key, size_bytes=len(converted), alt_text=alt_text.strip())
            job.due_at = timezone.now() + timedelta(hours=24)
            job.save(update_fields=["due_at"])
            finish(typed, owner, page, actor, "public_page.asset_uploaded", asset_id=asset.pk)
            state = editor_state(typed, owner, page)
            return {"asset": next(row for row in state["assets"] if row["id"] == asset.pk), "state": state}
    except BaseException:
        Cleanup.objects.filter(pk=job_id, completed_at__isnull=True).update(due_at=timezone.now())
        raise


@transaction.atomic
def delete(kind, owner_id, asset_id, *, actor, version):
    typed, owner, actor, page = lock_state(kind, owner_id, actor, version)
    asset = get_object_or_404(typed.asset.objects.select_for_update(), pk=asset_id, page=page)
    if typed.asset_reference.objects.filter(asset=asset).exists():
        raise PageConflict("asset_referenced", gettext("A saved revision retains this image."))
    Cleanup.objects.update_or_create(object_key=asset.object_key, defaults={"owner_kind": kind,
        "owner_id": owner_id, "page_id": page.pk, "size_bytes": asset.size_bytes, "due_at": timezone.now(), "completed_at": None})
    asset.delete()
    finish(typed, owner, page, actor, "public_page.asset_deleted", asset_id=asset_id)
    # Cleanup runs after the committing transaction makes removal authoritative.
    return editor_state(typed, owner, page)


def owns(asset, kind, owner_id):
    from apps.inventory.public_image_storage import is_safe_object_key
    if not is_safe_object_key(asset.object_key):
        return False
    if asset.object_key.startswith(prefix(kind, owner_id, asset.page_id)):
        return True
    if kind == "makerspace":
        from apps.tenant_migration.models_import_objects import TenantImportObject
        return TenantImportObject.objects.filter(target_key=asset.object_key, bucket_kind="private",
            job__target_makerspace_id=owner_id, state__in=("promoted", "verified")).exists()
    return False


def public_asset_ids(revision):
    doc = revision.document
    ids = {doc["cover_asset_id"]} if doc["cover_mode"] == "asset" else set()
    for section in doc["sections"]:
        if section["enabled"] and section["type"] == "gallery":
            ids.update(row["asset_id"] for row in section["payload"]["items"])
    return ids
