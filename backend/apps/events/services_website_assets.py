"""Private asset writes share the durable quota/copy/cleanup boundary."""

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError

from apps.makerspaces import website_assets
from apps.makerspaces.resource_clone import clone_transaction

from .event_permissions import EDIT_DETAILS
from .models_website import EventPageAsset
from .services_website import audit, bump, locked_target, own_page
from .website_copy import owner


def upload_asset(target, *, actor, file, alt_text, replace_id=None):
    if not isinstance(alt_text, str) or not alt_text.strip() or len(alt_text) > 200:
        raise ValidationError({"alt_text": "Provide an image description of at most 200 characters."})
    with clone_transaction() as copies:
        target, actor = locked_target(target, actor, EDIT_DETAILS)
        page = own_page(target, copies)
        old = get_object_or_404(page.assets, pk=replace_id) if replace_id else None
        if page.assets.count() >= 100 and old is None:
            raise ValidationError("A page may have at most 100 images.")
        key, size = website_assets.upload(file, module="events", page=page, copies=copies)
        asset = EventPageAsset.objects.create(page=page, object_key=key,
                                               size_bytes=size, alt_text=alt_text)
        if old:
            page.sections.filter(asset=old).update(asset=asset)
            old.delete()
            transaction.on_commit(lambda: website_assets.release(page.makerspace, old.object_key, old.size_bytes), robust=True)
        bump(page, target)
        audit(page, actor, "event.website_asset_saved", revision=page.revision)
        return asset


@transaction.atomic
def delete_asset(target, asset_id, *, actor):
    target, actor = locked_target(target, actor, EDIT_DETAILS)
    from .models_website import EventPage
    page = get_object_or_404(EventPage.objects.select_for_update(), **owner(target))
    asset = get_object_or_404(page.assets, pk=asset_id)
    key, size = asset.object_key, asset.size_bytes
    asset.delete()
    bump(page, target)
    audit(page, actor, "event.website_asset_removed", revision=page.revision)
    transaction.on_commit(lambda: website_assets.release(page.makerspace, key, size), robust=True)


def schedule_occurrence_asset_cleanup(event):
    """Capture owned keys before recurrence deletes an occurrence's page graph."""
    for key, size in EventPageAsset.objects.filter(page__event=event).values_list("object_key", "size_bytes"):
        transaction.on_commit(
            lambda key=key, size=size: website_assets.release(event.makerspace, key, size),
            robust=True,
        )
