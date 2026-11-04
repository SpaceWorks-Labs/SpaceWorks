"""Resource-locked, audited editorial writes with optimistic page revisions."""

from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.audit.services import record
from apps.makerspaces.resource_grant_locks import lock_tenant_authority
from . import booking_authority
from .admission import require_feature
from .models_website import BookingResourcePage, BookingResourcePageSection
from .serializers_website import BookingWebsiteContentInput, BookingWebsiteReleaseInput
from .services_bookings import _locked_space


def locked_target(space, actor, permission):
    space = _locked_space(space.pk)
    actor = lock_tenant_authority(actor, space)
    booking_authority.require(actor, space, permission)
    require_feature(space, "bookings.website")
    return space, actor


def own_page(space):
    return BookingResourcePage.objects.get_or_create(space=space)[0]


def bump(page, actor, action):
    page.revision += 1
    page.save(update_fields=["revision", "released", "updated_at"])
    record(actor=actor, action=action, makerspace=page.makerspace, target=page,
           meta={"revision": page.revision})


@transaction.atomic
def save_content(space, *, actor, data):
    serializer = BookingWebsiteContentInput(data=data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    space, actor = locked_target(space, actor, "edit_details")
    page = BookingResourcePage.objects.select_for_update().filter(space=space).first()
    if data["revision"] != (page.revision if page else 0):
        raise ValidationError({"revision": "The page changed. Reload before saving."})
    sections = data["sections"]
    if len({row["slug"] for row in sections}) != len(sections):
        raise ValidationError("Section slugs must be unique.")
    assets = set(page.assets.values_list("pk", flat=True)) if page else set()
    if any(row["asset_id"] is not None and row["asset_id"] not in assets for row in sections):
        raise ValidationError("Images must belong to this page.")
    page = page or own_page(space)
    page.sections.all().delete()
    for row in sections:
        BookingResourcePageSection.objects.create(page=page, **row)
    bump(page, actor, "booking.website_saved")
    return space


@transaction.atomic
def set_release(space, *, actor, data):
    serializer = BookingWebsiteReleaseInput(data=data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    space, actor = locked_target(space, actor, "publish_page")
    page = BookingResourcePage.objects.select_for_update().filter(space=space).first()
    if page is None or data["revision"] != page.revision:
        raise ValidationError({"revision": "Save the page and reload before releasing it."})
    if data["released"] and not (space.is_active and space.is_public):
        raise ValidationError("Only an active public resource can release its website.")
    page.released = data["released"]
    bump(page, actor, "booking.website_released" if page.released else "booking.website_unreleased")
    return space
