"""Files attached to a machine type's training notes (decision 343 follow-up).

The same private-upload path as machine documents (`machines.storage`: a presign on the staging key,
finalize and validate on attach, short-lived signed reads), plus storage accounting: attaching charges
the space's storage (refused when full), removing frees it. Members see a document only while it is
member-visible and they hold an active membership of the space.
"""

from django.conf import settings
from django.db import transaction
from django.utils.translation import gettext
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit
from apps.makerspaces import limits
from apps.makerspaces.guards import require_module_locked
from apps.makerspaces.models import Makerspace
from apps.makerspaces.storage_reservations import claimed_receipt, deletion_claim, object_operation

from . import storage
from .models_type_setup import MachineTypeDocument


def presign(space, content_type, filename, size=None):
    ext = storage.ext_for(content_type, filename)
    object_key = storage.machine_object_key(space.pk, ext)
    limits.check_upload_headroom(space)  # refuse before the upload when storage is full
    return object_key, storage.presigned_upload(object_key, content_type, **({"exact_bytes": size} if size is not None else {}))


@transaction.atomic
def attach(actor, space, machine_type, *, object_key, title, original_filename, member_visible=True):
    storage.assert_machine_object_key_for_makerspace(object_key, space.pk)
    if MachineTypeDocument.objects.filter(object_key=object_key).exists():
        raise ValidationError({"object_key": gettext("This upload is already attached.")})
    title = str(title or original_filename or "").strip()[:200]
    if not title:
        raise ValidationError({"title": gettext("Give the document a title.")})
    storage.finalize_upload(object_key, settings.MACHINE_DOC_MAX_BYTES)
    result = storage.validate_machine_object(object_key)
    limits.charge_upload(space, result.size, object_key=object_key)
    row = MachineTypeDocument.objects.create(
        makerspace=space, machine_type=machine_type, title=title, object_key=object_key,
        original_filename=str(original_filename or "")[:255], content_type=result.content_type,
        size_bytes=result.size, member_visible=bool(member_visible))
    audit.record(actor, "machine_type_document.added", makerspace=space, target=machine_type,
                 meta={"title": title, "size_bytes": row.size_bytes})
    return row


def remove(actor, row):
    identity = {"pk": row.pk, "makerspace_id": row.makerspace_id, "machine_type_id": row.machine_type_id}
    found = MachineTypeDocument.objects.filter(**identity).first()
    if found is None:
        return
    with object_operation(found.object_key):
        with transaction.atomic():
            space = Makerspace.objects.select_for_update().get(pk=row.makerspace_id)
            require_module_locked(space, "machines")
            found = MachineTypeDocument.objects.select_for_update().filter(**identity).first()
            if found is None:
                return
            receipt, version = deletion_claim(
                space, found.object_key, found.size_bytes, charged=True, bounded_upload=True)
        # Provider work cannot hold a tenant or document row lock.
        if storage.delete_object(found.object_key) is not None:
            raise storage.StorageUnavailable
        with transaction.atomic():
            space = Makerspace.objects.select_for_update().get(pk=row.makerspace_id)
            require_module_locked(space, "machines")
            fresh = MachineTypeDocument.objects.select_for_update().filter(**identity).first()
            receipt = claimed_receipt(receipt, version)
            if (fresh is None or receipt is None or fresh.object_key != found.object_key
                    or fresh.size_bytes != found.size_bytes):
                return
            limits.free_storage(space, fresh.size_bytes)
            receipt.released, receipt.cleaning = True, False
            receipt.save(update_fields=["released", "cleaning"])
            machine_type, title = fresh.machine_type, fresh.title
            fresh.delete()
            audit.record(actor, "machine_type_document.removed", makerspace=space,
                         target=machine_type, meta={"title": title})


def member_documents(space, machine_type):
    return MachineTypeDocument.objects.filter(makerspace=space, machine_type=machine_type, member_visible=True)


def signed_url(row):
    return storage.presigned_get_url(row.object_key)
