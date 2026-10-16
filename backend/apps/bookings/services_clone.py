"""Explicit resource configuration clone; authority and reservation history stay put."""

from django.conf import settings

from apps.accounts import rbac
from apps.makerspaces.resource_clone import OwnedImage, clone_transaction, copy_fields
from apps.makerspaces.resource_clone_extensions import copy_extensions

from . import booking_authority, storage
from .admission import require_feature
from .models import BookableSpace
from .services_bookings import _audit, _locked_space
from .services_rules import RULE_FIELDS
from .services_spaces import _canonical_form, _machine_type, _validate

COPY_FIELDS = frozenset({
    "name", "kind", "description", "capacity", "location", "custom_form",
    "payment_amount", "requester_notifications_enabled", "pass_template",
})


def clone_space(space, *, actor, copy_booking_rules=False):
    from rest_framework.exceptions import ValidationError
    if type(copy_booking_rules) is not bool:
        raise ValidationError({"copy_booking_rules": "Must be a boolean."})
    with clone_transaction() as assets:
        source = _locked_space(space.pk)
        booking_authority.require_tenant(actor, source.makerspace)
        require_feature(source, "bookings.clone")
        values = copy_fields(source, COPY_FIELDS)
        values["name"] = source.name[:193].rstrip() + " (copy)"
        values["custom_form"] = _canonical_form(values["custom_form"])
        if copy_booking_rules:
            booking_authority.require_tenant(actor, source.makerspace, action=rbac.Action.MANAGE_MAKERSPACE)
            values.update(copy_fields(source, RULE_FIELDS))
        clone = BookableSpace(
            makerspace=source.makerspace, created_by=actor, is_active=True, is_public=False,
            machine_type=_machine_type(source.makerspace, source.machine_type_id), **values,
        )
        _validate(clone)
        clone.save()
        clone.image_key = assets.copy_image(source.makerspace, OwnedImage(
            source_key=source.image_key, source_prefix=storage.owned_prefix(source),
            destination_prefix=storage.owned_prefix(clone), max_bytes=settings.PUBLIC_IMAGE_MAX_BYTES,
        ), storage=storage) or None
        if clone.image_key:
            clone.save(update_fields=["image_key", "updated_at"])
        # BK-F registers its website copier; it must leave the new page unreleased.
        copy_extensions("bookings", source, clone, assets)
        _audit(clone, actor, "booking.space_cloned", clone,
               {"source_space_id": source.pk, "copy_booking_rules": copy_booking_rules})
        return clone
