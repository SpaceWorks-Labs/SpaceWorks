"""Warranty writes, each re-checking the actor's authority under row locks.

The views authorize through plain lookups (`access.py`). Every write here runs that
authority again inside its transaction, after taking the tenant and authority locks
(`makerspaces.authority_lock`) and then the warranty's host row, so a role edit, a removed
membership or operator assignment, or a revoked organization grant that commits between
the view's check and the write cannot let it land. Lock order: makerspace -> membership
and roles -> organizations -> host (asset or machine) -> warranty -> document.
"""

from django.utils.translation import gettext
from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.accounts import rbac
from apps.audit import services as audit
from apps.inventory.models import InventoryAsset
from apps.machines import access as machine_access
from apps.machines.models import Machine
from apps.makerspaces.authority_lock import ACCESS_CHANGED, require_under_lock
from apps.makerspaces.guards import require_module
from apps.makerspaces.folded_capabilities import INVENTORY_WARRANTY, MACHINES_WARRANTY, require_capability
from apps.warranty import storage
from apps.warranty.models import Warranty, WarrantyDocument


def _locked_host(actor, kind, host):
    """Authority locks, then the host row, then the view's own predicate on fresh rows."""
    makerspace_id = host.makerspace_id
    if kind == "asset":
        require_under_lock(
            actor, makerspace_id,
            lambda: rbac.can(actor, rbac.Action.EDIT_INVENTORY, makerspace_id),
        )
        locked = InventoryAsset.objects.select_for_update(no_key=True).get(pk=host.pk)
        require_module(makerspace_id, "staff_admin")
        require_capability(makerspace_id, INVENTORY_WARRANTY)
        return locked
    # Machine authority is object-level (role scope, type manager or operator row), and
    # operator assignments lock the machine, so it is evaluated after that lock.
    require_under_lock(actor, makerspace_id, lambda: True)
    locked = (
        Machine.objects.select_for_update(no_key=True, of=("self",))
        .select_related("machine_type").get(pk=host.pk)
    )
    if not machine_access.can_manage_machine(actor, locked):
        raise PermissionDenied(ACCESS_CHANGED)
    require_capability(makerspace_id, MACHINES_WARRANTY)
    return locked


def _locked_warranty(actor, warranty_pk):
    warranty = Warranty.objects.select_related("asset", "machine").get(pk=warranty_pk)
    if warranty.asset_id:
        _locked_host(actor, "asset", warranty.asset)
    else:
        _locked_host(actor, "machine", warranty.machine)
    return (
        Warranty.objects.select_for_update(no_key=True, of=("self",))
        .select_related("makerspace").get(pk=warranty_pk)
    )


def _vendor(makerspace_id, vendor_id):
    """The saved supplier link (L12): a live vendor of this space, behind `inventory.vendors`."""
    if vendor_id is None:
        return None
    from apps.makerspaces.folded_capabilities import require_capability
    from apps.procurement.models import Vendor
    require_capability(makerspace_id, "inventory.vendors")
    vendor = Vendor.objects.filter(pk=vendor_id, makerspace_id=makerspace_id, is_archived=False).first()
    if vendor is None:
        raise ValidationError({"vendor_id": gettext("Choose a vendor of this makerspace.")})
    return vendor


@transaction.atomic
def upsert_warranty(actor, *, data, asset=None, machine=None):
    hosts = [(kind, host) for kind, host in (("asset", asset), ("machine", machine)) if host is not None]
    if len(hosts) != 1:
        raise ValueError("Exactly one warranty host is required.")
    kind, host = hosts[0]
    host = _locked_host(actor, kind, host)
    warranty, created = Warranty.objects.get_or_create(
        **{kind: host}, defaults={"makerspace_id": host.makerspace_id},
    )
    warranty.makerspace_id = host.makerspace_id
    for field in ("purchased_on", "warranty_expires_on", "vendor_name", "vendor_contact"):
        if field in data:
            setattr(warranty, field, data[field])
    if "vendor_id" in data:
        warranty.vendor = _vendor(host.makerspace_id, data["vendor_id"])
    try:
        warranty.full_clean()
    except DjangoValidationError as exc:
        raise ValidationError(getattr(exc, "message_dict", exc.messages)) from exc
    warranty.save()
    audit.record(
        actor, "warranty.created" if created else "warranty.updated",
        makerspace=host.makerspace, target=warranty,
    )
    return warranty, created


@transaction.atomic
def presign_document(actor, warranty, data):
    """Issue a staging upload URL only while the actor still manages the warranty."""
    locked = _locked_warranty(actor, warranty.pk)
    ext = storage.ext_for(data["content_type"], data["filename"])
    object_key = storage.warranty_object_key(locked.makerspace_id, ext)
    upload = storage.presigned_upload(object_key, data["content_type"])
    return {"object_key": object_key, "upload": upload}


@transaction.atomic
def finalize_document(actor, warranty, data):
    locked = _locked_warranty(actor, warranty.pk)
    object_key = data["object_key"]
    storage.assert_warranty_object_key_for_makerspace(object_key, locked.makerspace_id)
    if WarrantyDocument.objects.filter(object_key=object_key).exists():
        raise ValidationError({"object_key": gettext("This warranty document is already attached.")})
    storage.finalize_upload(object_key, settings.WARRANTY_DOC_MAX_BYTES)
    result = storage.validate_warranty_object(object_key)
    document = WarrantyDocument.objects.create(
        warranty=locked,
        object_key=object_key,
        original_filename=data["original_filename"],
        content_type=result.content_type,
        size_bytes=result.size,
        uploaded_by=actor,
    )
    audit.record(actor, "warranty.document_added", makerspace=locked.makerspace, target=document)
    return document


@transaction.atomic
def delete_document(actor, document):
    locked_warranty = _locked_warranty(actor, document.warranty_id)
    locked = WarrantyDocument.objects.select_for_update().filter(
        pk=document.pk, warranty=locked_warranty,
    ).first()
    if locked is None:
        raise NotFound()
    audit.record(
        actor, "warranty.document_removed",
        makerspace=locked_warranty.makerspace, target=locked,
    )
    # The post_delete signal removes the stored object after commit (covers every delete
    # path, including host/warranty CASCADE), so it is not deleted explicitly here.
    locked.delete()
