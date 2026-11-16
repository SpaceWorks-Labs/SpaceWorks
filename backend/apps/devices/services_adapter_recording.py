"""Opt-in camera-watch recording: a presigned upload, retention-limited, deleted with confirmation (M3).

Where the bytes live: the presign signs the STAGING key of ``adapter-recordings/<space>/<watch>`` (Hard Rule: the
final key is never client-writable) and nothing promotes it, because no route ever serves a recording back. The
staging key is therefore the recording's only home. Retention (``purge_recordings``) and the devices module purge
(``makerspaces.module_purge_collectors_devices.devices_private_keys``) still delete BOTH keys, every version.

Only ``video/webm`` and ``video/mp4`` are accepted, and the signed upload itself enforces ``RECORDING_MAX_BYTES``.
A watch is stamped ``recording_purged_at`` only after storage confirmed both keys are gone; a failure is logged and
the row stays due, so the next sweep retries instead of an audit row claiming bytes are gone that are not.
"""
import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext
from rest_framework.exceptions import PermissionDenied

from apps.audit import services as audit
from apps.devices.adapter_access import require_adapters
from apps.devices.adapters.caps.media_stream import RECORDING
from apps.devices.models import AdapterWatch
from apps.devices.services_adapter_core import AdapterError, audit_adapter, check

logger = logging.getLogger(__name__)
RECORDING_SWITCH = "machines.integrations.recording"
RECORDING_DAYS = 7
RECORDING_CONTENT_TYPES = frozenset({"video/webm", "video/mp4"})
RECORDING_MAX_BYTES = 512 * 1024 * 1024  # = the RECORDING schema's size_bytes cap, bound into the signed upload


def _presign(key, content_type):
    """Sign the staging key with the recording's own size cap (the evidence presign carries the photo cap)."""
    from botocore.exceptions import BotoCoreError, ClientError

    from apps.evidence import storage
    from apps.storage_capabilities import CapabilityError
    from apps.storage_capabilities.presigning import presign_upload
    try:
        return presign_upload(
            storage._public_client(), backend_client=storage._client(), bucket=settings.AWS_STORAGE_BUCKET_NAME,
            key=storage.staging_key(key), content_type=content_type, max_bytes=RECORDING_MAX_BYTES,
            ttl=settings.EVIDENCE_URL_TTL_SECONDS, requested=settings.STORAGE_PRESIGN_METHOD)
    except (BotoCoreError, ClientError, CapabilityError) as exc:
        raise storage.StorageUnavailable from exc


def recording_upload(principal, watch_id, body):
    from apps.devices.services_adapter_media import _adapter_watch, _live
    from apps.evidence.storage import StorageUnavailable
    check(RECORDING, body, label="recording")
    content_type = str(body["content_type"]).strip().lower()
    if content_type not in RECORDING_CONTENT_TYPES:  # a typed 400, like artifacts (errors.md)
        raise AdapterError("content_type_not_allowed", "A recording must be video/webm or video/mp4.")
    with transaction.atomic():
        watch = _adapter_watch(principal, watch_id)
        _live(watch)
        require_adapters(watch.makerspace_id, RECORDING_SWITCH)
        if not watch.record:
            raise PermissionDenied(gettext("Recording was not requested for this watch."))
        key = f"adapter-recordings/{watch.makerspace_id}/{watch.pk}"
        try:
            upload = _presign(key, content_type)
        except StorageUnavailable as exc:
            raise AdapterError("storage_unavailable", "Storage is unavailable; retry.", status_code=503) from exc
        watch.recording_key = key
        watch.recording_expires_at = timezone.now() + timedelta(days=RECORDING_DAYS)
        watch.save(update_fields=["recording_key", "recording_expires_at"])
        audit_adapter(watch.makerspace, watch.binding.device, "devices.adapter_watch_recording_stored",
                      meta={"watch_id": str(watch.pk), "expires_at": watch.recording_expires_at.isoformat()})
    return {"upload_url": upload["url"], "fields": upload.get("fields", {}), "object_key": key,
            "expires_at": int(watch.recording_expires_at.timestamp())}


def due_recordings(now):
    return AdapterWatch.objects.filter(recording_expires_at__lte=now, recording_purged_at__isnull=True).exclude(
        recording_key="")


def purge_recordings(now=None, space_id=None):
    """Delete every recording past retention (idempotent); the watch row and audit trail remain."""
    from apps.machines.service_storage import purge_upload
    now = now or timezone.now()
    done, rows = 0, due_recordings(now)
    for watch in (rows.filter(makerspace_id=space_id) if space_id else rows)[:200]:
        try:
            purge_upload(watch.recording_key)  # final AND staging, every version, confirmed
        except Exception:  # noqa: BLE001 - logged and left due: the next sweep retries
            logger.warning("adapter_recording_purge_failed", extra={"watch_id": str(watch.pk)}, exc_info=True)
            continue
        AdapterWatch.objects.filter(pk=watch.pk).update(recording_purged_at=now)
        audit.record(None, "devices.adapter_watch_recording_purged", makerspace=watch.makerspace,
                     target=watch.binding, meta={"watch_id": str(watch.pk)})
        done += 1
    return done
