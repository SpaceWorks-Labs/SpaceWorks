"""Camera watch sessions (media.snapshot / media.stream): staff-initiated, short-lived, audited and limited.

Privacy rules (FABMAN-RESEARCH 9.5): the adapter only ever sends frames while a watch session is open; a watch
lasts five minutes unless renewed; each start is an audit row naming the viewer; the number of concurrent watches and
of snapshots per month are limit keys (default none). Media never persists on the server (no recording in this
release) and nothing here is reachable by anyone without MANAGE_DEVICES plus the machine scope.
"""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.devices.adapter_access import VIDEO_SWITCH, scoped_binding
from apps.devices.models import AdapterWatch
from apps.devices.services_adapter_commands import enqueue
from apps.devices.services_adapter_core import AdapterError
from apps.devices.services_locks import lock_tenant
from apps.managed_hosting.extra_quotas import check_extra_quota

WATCH_SECONDS = 300
VIDEO_CAPABILITIES = ("media.stream", "media.snapshot")


def start_watch(actor, binding_id, reason="", record=False, *, audio=False, talk=False, notice_ack=False):
    from apps.devices.services_adapter_media import start_staff
    binding = scoped_binding(actor, binding_id, child=VIDEO_SWITCH)
    if not any(name in binding.capabilities for name in VIDEO_CAPABILITIES):
        raise AdapterError("capability_missing", "This binding has no camera capability.", status_code=409)
    return start_staff(actor, binding, reason, record, audio=audio, talk=talk, notice_ack=notice_ack)


def _owned(actor, watch_id):
    watch = AdapterWatch.objects.select_related("binding").filter(pk=watch_id).first()
    if watch is None:
        from rest_framework.exceptions import NotFound
        raise NotFound()
    scoped_binding(actor, watch.binding_id, child=VIDEO_SWITCH)  # tenant/scope/switch check: 404 or 403
    return watch


def request_snapshot(actor, watch_id):
    """Ask the adapter for one still; allowed only while the watch is open (no watch, no frame)."""
    watch = _owned(actor, watch_id)
    if watch.status != AdapterWatch.Status.ACTIVE or watch.expires_at <= timezone.now():
        raise AdapterError("watch_ended", "This watch session has ended.", status_code=409)
    if "media.snapshot" not in watch.binding.capabilities:
        raise AdapterError("capability_missing", "This binding cannot take snapshots.", status_code=409)
    check_extra_quota(watch.makerspace, "adapter_snapshots")
    return enqueue(actor, watch.binding_id, "media.snapshot", "snapshot", {"watch_id": str(watch.pk)})


def end_watch(actor, watch_id):
    watch = _owned(actor, watch_id)
    with transaction.atomic():
        AdapterWatch.objects.filter(pk=watch.pk, status=AdapterWatch.Status.ACTIVE).update(
            status=AdapterWatch.Status.ENDED, ended_at=timezone.now())
        audit.record(actor, "devices.adapter_watch_ended", makerspace=watch.makerspace, target=watch.binding.device,
                     meta={"device_id": str(watch.binding.device_id), "watch_id": str(watch.pk)})
    watch.refresh_from_db()
    return watch
