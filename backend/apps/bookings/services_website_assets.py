"""Private gallery writes use the shared durable storage transaction."""

from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError

from apps.makerspaces import website_assets
from apps.makerspaces.resource_clone import clone_transaction
from apps.makerspaces.website_serving import private_image_response
from .models_website import BookingResourcePage, BookingResourcePageAsset
from .services_website import bump, locked_target, own_page


def upload_asset(space, *, actor, file, alt_text, replace_id=None):
    if not isinstance(alt_text, str) or not alt_text.strip() or len(alt_text) > 200:
        raise ValidationError({"alt_text": "Provide an image description of at most 200 characters."})
    with clone_transaction() as copies:
        space, actor = locked_target(space, actor, "edit_details")
        page = own_page(space)
        old = get_object_or_404(page.assets, pk=replace_id) if replace_id else None
        if page.assets.count() >= 100 and old is None:
            raise ValidationError("A page may have at most 100 images.")
        key, size = website_assets.upload(file, module="bookings", page=page, copies=copies)
        asset = BookingResourcePageAsset.objects.create(page=page, object_key=key,
                                                        size_bytes=size, alt_text=alt_text.strip())
        if old:
            page.sections.filter(asset=old).update(asset=asset)
            key_old, size_old = old.object_key, old.size_bytes
            old.delete()
            transaction.on_commit(lambda: website_assets.release(page.makerspace, key_old, size_old), robust=True)
        bump(page, actor, "booking.website_asset_saved")
        return asset


@transaction.atomic
def delete_asset(space, asset_id, *, actor):
    space, actor = locked_target(space, actor, "edit_details")
    page = get_object_or_404(BookingResourcePage.objects.select_for_update(), space=space)
    asset = get_object_or_404(page.assets, pk=asset_id)
    key, size = asset.object_key, asset.size_bytes
    asset.delete()
    bump(page, actor, "booking.website_asset_removed")
    transaction.on_commit(lambda: website_assets.release(page.makerspace, key, size), robust=True)


def image_response(asset):
    if not website_assets.owns(asset.object_key, "bookings", asset.page.makerspace_id, asset.page_id, asset=asset):
        raise Http404
    return private_image_response(asset.object_key)
