"""Reusable evidence row creation + direct-to-staging presign.

Shared by the staff upload-URL endpoint and the phase 9b kiosk evidence route. The
presign targets the staging key (``presigned_upload`` binds it); the final object key is
never client-writable and a workflow promotes it exactly once. There is no backend blob
proxy: the browser uploads directly.
"""

import logging

from django.db import transaction
from django.utils.translation import gettext
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit
from apps.evidence.models import EvidencePhoto
from apps.evidence.storage import evidence_object_key, presigned_upload

logger = logging.getLogger(__name__)
_USE_UPLOADER = object()


def upload_maximum(makerspace, size_bytes):
    """Caller holds the tenant lock; initial and legacy evidence share one bound."""
    from django.conf import settings
    from apps.makerspaces.limits import resource_limit
    from apps.makerspaces.limits_uploads import check_upload_size, upload_cap
    from apps.makerspaces.limits_usage import _storage
    from apps.managed_hosting.extra_quotas import extra_used

    check_upload_size(makerspace, size_bytes)
    maximum = min(size_bytes or settings.EVIDENCE_MAX_BYTES, settings.EVIDENCE_MAX_BYTES)
    cap = upload_cap(makerspace)
    if cap is not None:
        check_upload_size(makerspace, 1)
        maximum = min(maximum, cap)
    if size_bytes is None:
        for key, used in (("storage", _storage(makerspace)),
                          ("storage_evidence_bytes", extra_used(makerspace, "storage_evidence_bytes"))):
            budget = resource_limit(makerspace, key)
            if budget is not None:
                # Admit at least one byte through reserve so an exhausted budget
                # retains its normal combined/class error, without signing.
                maximum = min(maximum, max(1, budget - used))
    return maximum


def issue_upload(
    makerspace, *, actor, evidence_type, content_type, size_bytes=None, size=None,
    audit_action="evidence.upload_url_issued", audit_meta=None,
    consumption_state=EvidencePhoto.ConsumptionState.LEGACY_UNKNOWN,
    audit_actor=_USE_UPLOADER, presigner=None,
):
    """Create the immutable EvidencePhoto row and return ``(photo, response data)``.

    Raises ``apps.evidence.storage.StorageUnavailable`` before any row is written when
    object storage cannot presign; callers map it to their 503 response.
    ``consumption_state`` stays ``legacy_unknown`` (never a cleanup candidate) unless the
    caller is a production presign view that opts its rows into abandoned-upload cleanup.
    """
    from django.conf import settings
    from apps.makerspaces.models import Makerspace
    from apps.makerspaces.storage_reservations import reserve, cover_authorization
    from apps.evidence.storage import staging_key

    if size is not None:
        size_bytes = size
    if size_bytes is not None and (type(size_bytes) is not int or not 1 <= size_bytes <= settings.EVIDENCE_MAX_BYTES):
        raise ValidationError({"code": "upload_limit", "detail": gettext(
            "Upload size must be between 1 and {maximum} bytes.").format(maximum=settings.EVIDENCE_MAX_BYTES)})
    object_key = evidence_object_key(makerspace.pk, evidence_type)
    with transaction.atomic():
        locked = Makerspace.objects.select_for_update(no_key=True).get(pk=makerspace.pk)
        maximum = upload_maximum(locked, size_bytes)
        reserve(makerspace.pk, object_key, maximum, bucket=settings.AWS_STORAGE_BUCKET_NAME,
                staging_key=staging_key(object_key), ttl=settings.EVIDENCE_URL_TTL_SECONDS, kind="evidence")
        upload_options = {"max_bytes": maximum}
        if size_bytes is not None:
            upload_options["exact_bytes"] = size_bytes
        upload = (presigner or presigned_upload)(object_key, content_type, **upload_options)
        cover_authorization(object_key, settings.EVIDENCE_URL_TTL_SECONDS)
        photo = EvidencePhoto.objects.create(
            makerspace=makerspace,
            evidence_type=evidence_type,
            object_key=object_key,
            content_type=content_type,
            size_bytes=size_bytes,
            uploaded_by=actor,
            consumption_state=consumption_state,
        )
        meta = dict(audit_meta or {})
        if audit_meta is not None:
            meta["evidence_id"] = photo.pk
        audit.record(actor if audit_actor is _USE_UPLOADER else audit_actor, audit_action,
                     makerspace=makerspace, target=photo, meta=meta)
    logger.info(
        "evidence_upload_url_issued",
        extra={
            "evidence_id": photo.pk,
            "makerspace_id": makerspace.pk,
            "evidence_type": evidence_type,
        },
    )
    data = {
        "evidence_id": photo.pk,
        "upload_url": upload["url"],
        "fields": upload.get("fields", {}),
        "object_key": object_key,
    }
    if upload.get("method"):
        data["method"] = upload["method"]
        data["headers"] = upload.get("headers", {})
    return photo, data
