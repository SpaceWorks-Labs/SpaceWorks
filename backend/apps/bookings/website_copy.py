"""Explicit clone extension. Copied pages start unreleased and own fresh keys."""

from apps.makerspaces import website_assets
from apps.makerspaces.resource_clone import bounded_children, copy_fields
from .models_website import BookingResourcePage, BookingResourcePageAsset, BookingResourcePageSection
from .website_projection import SECTION_FIELDS


def copy_page(source, target, copies):
    original = BookingResourcePage.objects.select_for_update().filter(space=source).first()
    if original is None:
        return
    page = BookingResourcePage.objects.create(space=target)
    assets = {}
    for row in bounded_children(original.assets.select_related("page__space__makerspace")):
        key = website_assets.copy_asset(row, page, module="bookings", copies=copies)
        assets[row.pk] = BookingResourcePageAsset.objects.create(
            page=page, object_key=key, size_bytes=row.size_bytes, alt_text=row.alt_text)
    for row in bounded_children(original.sections.all()):
        BookingResourcePageSection.objects.create(page=page, asset=assets.get(row.asset_id),
                                                  **copy_fields(row, SECTION_FIELDS))
