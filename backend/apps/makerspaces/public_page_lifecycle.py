"""Retained typed private assets enlist durable cleanup before graph deletion.

The cleanup row's makerspace owner is the quota owner, also for event pages.
Its page ID and key are inert provenance; there is deliberately no event FK.
"""

from django.utils.translation import gettext
from django.utils import timezone


def enqueue_tenant_pages(makerspace, *, events_only=False):
    from .models_page_cleanup import PublicPageObjectCleanup as Cleanup
    from .models_public_pages import MakerspacePublicPageAsset
    from apps.events.models_website import EventPageAsset
    models = (EventPageAsset,) if events_only else (MakerspacePublicPageAsset, EventPageAsset)
    for model in models:
        for asset in model.objects.filter(page__makerspace=makerspace).iterator(chunk_size=100):
            if model is EventPageAsset:
                from .website_assets import owns
                valid = owns(asset.object_key, "events", makerspace.pk, asset.page_id, asset=asset)
            else:
                from .public_page_assets import owns
                valid = owns(asset, "makerspace", makerspace.pk)
            if not valid:
                from django.core.exceptions import ValidationError
                raise ValidationError(gettext("Cannot purge a page image without typed byte ownership."))
            if model is EventPageAsset:
                # Preserve the event owner and its checked import-key proof even
                # when a raw purge bypasses the asset's ORM pre_delete receiver.
                from .website_asset_journal import schedule
                schedule(asset)
                continue
            Cleanup.objects.update_or_create(object_key=asset.object_key, defaults={
                "owner_kind": "makerspace", "owner_id": makerspace.pk, "page_id": asset.page_id,
                "size_bytes": asset.size_bytes, "due_at": timezone.now(), "completed_at": None,
            })


def event_cleanup_keys():
    """Native and mapped event bytes must not consume a makerspace builder slot."""
    from django.db.models import Q
    from apps.tenant_migration.models_import_objects import TenantImportObject
    return Q(object_key__startswith="events/website/") | Q(object_key__in=
        TenantImportObject.objects.filter(source_key__startswith="events/website/").values("target_key"))
