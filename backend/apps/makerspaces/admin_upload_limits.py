"""Capacity validation shared by the two direct-upload control forms."""
from django.db import transaction
from rest_framework.exceptions import APIException

from apps.makerspaces.admin_limits import form_limit_error
from apps.makerspaces.limits import check_quota
from apps.makerspaces.limits_uploads import check_upload_headroom
from apps.makerspaces.models import Makerspace
from apps.managed_hosting.extra_quotas import check_storage_class


def validate_admin_uploads(makerspace, uploads):
    uploads = [upload for upload in uploads if upload]
    if not uploads or not makerspace.pk:
        return
    try:
        # The changeform transaction retains this lock through the actual upload
        # and storage charge. Two images in one form consume their combined size.
        with transaction.atomic():
            space = Makerspace.objects.select_for_update(no_key=True).get(pk=makerspace.pk)
            for upload in uploads:
                check_upload_headroom(space, size_bytes=upload.size)
            size = sum(upload.size for upload in uploads)
            # The combined storage budget applies to the whole form; the
            # per-file cap above applies independently to each image.
            check_quota(space, "storage", adding=size)
            check_storage_class(space, "storage_public_images_bytes", size)
    except APIException as exc:
        raise form_limit_error(exc) from exc
