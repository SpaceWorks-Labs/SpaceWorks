"""Vendor records: create, edit and archive (never delete; purchases keep their link).

Editing needs To-Buy authority in at least one stream here (the Space Manager, an
Inventory Manager, or a Machine Manager whose To-Buy stream is on), behind the
`inventory.vendors` switch. Every change is audited.
"""

from django.utils.translation import gettext
from django.db import IntegrityError, transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit import services as audit
from apps.makerspaces.folded_capabilities import require_capability_locked
from apps.procurement import access
from apps.procurement.models import Vendor

FEATURE = "inventory.vendors"
FIELDS = ("name", "contact_name", "email", "phone", "website", "notes")


def may_manage(actor, makerspace_id):
    return any(access.can_manage_kind(actor, makerspace_id, kind) for kind in access.switched_kinds(makerspace_id))


def _save(vendor):
    try:
        with transaction.atomic():
            vendor.full_clean()
            vendor.save()
    except IntegrityError:
        raise ValidationError({"name": gettext("A vendor with this name already exists.")}) from None
    except Exception as exc:
        from django.core.exceptions import ValidationError as DjangoValidationError
        if isinstance(exc, DjangoValidationError):
            if "__all__" in getattr(exc, "message_dict", {}):
                raise ValidationError({"name": gettext("A vendor with this name already exists.")}) from None
            raise ValidationError(exc.message_dict) from None
        raise
    return vendor


@transaction.atomic
def create_vendor(actor, makerspace, data):
    makerspace = require_capability_locked(makerspace, FEATURE)
    if not may_manage(actor, makerspace.pk):
        raise PermissionDenied()
    vendor = Vendor(makerspace=makerspace, created_by=actor, **{key: data.get(key, "") for key in FIELDS})
    _save(vendor)
    audit.record(actor, "vendor.created", makerspace=makerspace, target=vendor, meta={"vendor_id": vendor.pk})
    return vendor


@transaction.atomic
def update_vendor(actor, vendor, data):
    require_capability_locked(vendor.makerspace_id, FEATURE)
    locked = Vendor.objects.select_for_update().get(pk=vendor.pk)
    if not may_manage(actor, locked.makerspace_id):
        raise PermissionDenied()
    changed = sorted(key for key in FIELDS if key in data and getattr(locked, key) != data[key])
    for key in changed:
        setattr(locked, key, data[key])
    if "is_archived" in data and locked.is_archived != data["is_archived"]:
        locked.is_archived = data["is_archived"]
        changed.append("is_archived")
    if changed:
        _save(locked)
        if changed == ["is_archived"] and locked.is_archived:
            audit.record(actor, "vendor.archived", makerspace=locked.makerspace, target=locked,
                         meta={"vendor_id": locked.pk, "fields": changed})
        else:
            audit.record(actor, "vendor.updated", makerspace=locked.makerspace, target=locked,
                         meta={"vendor_id": locked.pk, "fields": changed})
    return locked
