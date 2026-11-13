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

from . import storage
from .models_type_setup import MachineTypeDocument


def presign(space, content_type, filename):
    ext = storage.ext_for(content_type, filename)
    object_key = storage.machine_object_key(space.pk, ext)
    limits.check_upload_headroom(space)  # refuse before the upload when storage is full
    return object_key, storage.presigned_upload(object_key, content_type)


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
    limits.add_storage(space, result.size)
    row = MachineTypeDocument.objects.create(
        makerspace=space, machine_type=machine_type, title=title, object_key=object_key,
        original_filename=str(original_filename or "")[:255], content_type=result.content_type,
        size_bytes=result.size, member_visible=bool(member_visible))
    audit.record(actor, "machine_type_document.added", makerspace=space, target=machine_type,
                 meta={"title": title, "size_bytes": row.size_bytes})
    return row


@transaction.atomic
def remove(actor, row):
    space, machine_type, size, key, title = row.makerspace, row.machine_type, row.size_bytes, row.object_key, row.title
    row.delete()
    limits.free_storage(space, size)
    transaction.on_commit(lambda: storage.delete_object(key))
    audit.record(actor, "machine_type_document.removed", makerspace=space, target=machine_type, meta={"title": title})


def member_documents(space, machine_type):
    return MachineTypeDocument.objects.filter(makerspace=space, machine_type=machine_type, member_visible=True)


def signed_url(row):
    return storage.presigned_get_url(row.object_key)
