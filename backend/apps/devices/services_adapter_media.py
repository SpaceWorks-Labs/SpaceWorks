"""media.stream signaling relay, snapshot fallback and opt-in recording (decision 312 addenda).

The server only RELAYS WebRTC signaling (SDP offer/answer, ICE candidates) between the viewer and the adapter
under an ``AdapterWatch``; media never touches the server. A watch lasts five minutes. Who may watch: staff with
MANAGE_DEVICES and the machine scope (``services_adapter_watch.start_watch``), or the owner of the in-progress
request running on that machine (``start_for_job_owner``). Snapshots are accepted only while a watch is open and
live for a minute in the cache. Recording is opt-in per watch, needs ``machines.integrations.recording``, is audited
at every step and expires (``RECORDING_DAYS``) via ``purge_recordings``.
"""
from django.utils.translation import gettext
import base64
import hashlib
import hmac
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied

from apps.audit import services as audit
from apps.devices.adapter_access import (AUDIO_RECORDING_SWITCH, AUDIO_SWITCH, TALK_SWITCH, VIDEO_SWITCH, adapter_device,
                                         authorize_staff, require_adapters)
from apps.devices.adapters.caps.media_snapshot import FRAME
from apps.devices.adapters.caps.media_stream import SIGNAL
from apps.devices.models import AdapterBinding, AdapterWatch
from apps.devices.services_adapter_core import AdapterError, check
from apps.devices.services_adapter_watch import WATCH_SECONDS, VIDEO_CAPABILITIES
from apps.devices.services_adapter_recording import RECORDING_DAYS, RECORDING_SWITCH  # noqa: F401 (re-export)
from apps.devices.services_locks import lock_tenant
from apps.managed_hosting.extra_quotas import check_extra_quota

MAX_SIGNALS = 60
MAX_PRESSES = 200
PTT_KINDS = ("ptt_on", "ptt_off")
FRAME_SECONDS = 60
MAX_FRAME_CHARS = 700_000


def ice_servers(watch):
    """Optional TURN (settings ``ADAPTER_TURN_URLS`` + ``ADAPTER_TURN_SECRET``): ephemeral REST credentials."""
    urls, secret = getattr(settings, "ADAPTER_TURN_URLS", []), getattr(settings, "ADAPTER_TURN_SECRET", "")
    if not urls or not secret:
        return []
    user = f"{int(watch.expires_at.timestamp())}:{watch.pk}"
    cred = base64.b64encode(hmac.new(secret.encode(), user.encode(), hashlib.sha1).digest()).decode()
    return [{"urls": list(urls), "username": user, "credential": cred}]


def _live(watch):
    if watch.status != AdapterWatch.Status.ACTIVE or watch.expires_at <= timezone.now():
        if watch.status == AdapterWatch.Status.ACTIVE:
            AdapterWatch.objects.filter(pk=watch.pk).update(status=AdapterWatch.Status.ENDED, ended_at=timezone.now())
        raise AdapterError("watch_ended", "This watch session has ended.", status_code=409)


def _append(watch, sender, body):
    signals = list(watch.signals)[-(MAX_SIGNALS - 1):]
    n = (signals[-1]["n"] + 1) if signals else 1
    signals.append({"n": n, "from": sender, "kind": body["kind"], "sdp": body.get("sdp", ""),
                    "candidate": body.get("candidate", "")})
    watch.signals = signals
    watch.save(update_fields=["signals"])
    return n


def _since(watch, sender, after):
    return [row for row in watch.signals if row["from"] == sender and row["n"] > after]


def adapter_signal(principal, watch_id, body):
    check(SIGNAL, body, label="signal")
    if body["kind"] in PTT_KINDS:
        raise AdapterError("invalid_payload", "Push-to-talk signals come from the viewer only.")
    with transaction.atomic():
        watch = _adapter_watch(principal, watch_id)
        _live(watch)
        return {"n": _append(watch, "adapter", body)}


def adapter_poll(principal, watch_id, after=0):
    with transaction.atomic():
        watch = _adapter_watch(principal, watch_id)
        _live(watch)
        return {"signals": _since(watch, "viewer", after), "ice_servers": ice_servers(watch),
                "record": watch.record, "audio": watch.audio, "talk": watch.talk,
                # The adapter must make the audio notice perceptible at the device (a chime, a light, a sign).
                "announce_audio": watch.audio or watch.talk, "expires_at": int(watch.expires_at.timestamp())}


def _adapter_watch(principal, watch_id):
    require_adapters(principal.makerspace_id, VIDEO_SWITCH)
    device = adapter_device(principal, lock=True)
    watch = AdapterWatch.objects.select_for_update().select_related("binding").filter(
        pk=watch_id, binding__device=device, makerspace_id=device.makerspace_id).first()
    if watch is None:
        raise NotFound()
    return watch


def viewer_watch(actor, watch_id):
    """The watch for its own viewer (staff or job owner); anyone else, or the switch off, is 404."""
    watch = AdapterWatch.objects.select_for_update().select_related("binding").filter(pk=watch_id).first()
    if watch is None or watch.viewer_id != actor.pk:
        raise NotFound()
    require_adapters(watch.makerspace_id, VIDEO_SWITCH)
    return watch


def viewer_signal(actor, watch_id, body):
    check(SIGNAL, body, label="signal")
    if body["kind"] in PTT_KINDS:
        raise AdapterError("invalid_payload", "Use the talk route for push-to-talk.")
    with transaction.atomic():
        watch = viewer_watch(actor, watch_id)
        _live(watch)
        return {"n": _append(watch, "viewer", body)}


def viewer_poll(actor, watch_id, after=0):
    with transaction.atomic():
        watch = viewer_watch(actor, watch_id)
        _live(watch)
        return {"signals": _since(watch, "adapter", after), "ice_servers": ice_servers(watch)}


def viewer_end(actor, watch_id):
    with transaction.atomic():
        watch = viewer_watch(actor, watch_id)
        AdapterWatch.objects.filter(pk=watch.pk, status=AdapterWatch.Status.ACTIVE).update(
            status=AdapterWatch.Status.ENDED, ended_at=timezone.now())
        audit.record(actor, "devices.adapter_watch_ended", makerspace=watch.makerspace, target=watch.binding.device,
                     meta={"device_id": str(watch.binding.device_id), "watch_id": str(watch.pk)})
    watch.refresh_from_db()
    return watch


def start_for_job_owner(actor, request_id, record=False):
    """The member whose in-progress request runs on a camera-equipped machine may watch it (and only it)."""
    from apps.machines.models import MachineServiceRequest
    request = MachineServiceRequest.objects.filter(pk=request_id).first()
    owner = request and (request.member_id or request.requester_id)
    if request is None or owner != actor.pk or request.status != MachineServiceRequest.Status.IN_PROGRESS:
        raise NotFound()
    binding = AdapterBinding.objects.select_related("device").filter(
        machine_id=request.assigned_machine_id, makerspace_id=request.makerspace_id, enabled=True,
        device__status="active").first()
    if binding is None or not any(name in binding.capabilities for name in VIDEO_CAPABILITIES):
        raise NotFound()
    require_adapters(binding.makerspace_id, VIDEO_SWITCH)
    watch = _open(actor, binding, "job_owner", record=False)
    audit.record(actor, "devices.adapter_watch_viewed", makerspace=watch.makerspace, target=binding.device,
                 meta={"watch_id": str(watch.pk), "service_request_id": request.pk})
    return watch


def _open(actor, binding, reason, *, record, audio=False, talk=False, notice_ack=False):
    with transaction.atomic():
        makerspace = lock_tenant(binding.makerspace_id)
        check_extra_quota(makerspace, "adapter_watch_streams")
        if record:
            require_adapters(makerspace.pk, RECORDING_SWITCH)
        talk = _audio_gate(makerspace.pk, binding, audio=audio, talk=talk, record=record, notice_ack=notice_ack)
        audio = audio or talk
        now = timezone.now()
        watch = AdapterWatch.objects.create(
            makerspace=makerspace, binding=binding, viewer=actor, record=record, audio=audio, talk=talk,
            audio_notice_ack=notice_ack, expires_at=now + timedelta(seconds=WATCH_SECONDS))
        if audio:
            audit.record(actor, "devices.adapter_audio_started", makerspace=makerspace, target=binding.device, meta={
                "device_id": str(binding.device_id), "watch_id": str(watch.pk), "talk": talk, "record": record,
                "notice_acknowledged": notice_ack})
        audit.record(actor, "devices.adapter_watch_started", makerspace=makerspace, target=binding.device, meta={
            "device_id": str(binding.device_id), "binding_id": str(binding.pk), "watch_id": str(watch.pk),
            "reason": reason[:120], "record": record})
        if record:
            audit.record(actor, "devices.adapter_watch_recording_requested", makerspace=makerspace,
                         target=binding.device, meta={"watch_id": str(watch.pk)})
    return watch


def _audio_gate(makerspace_id, binding, *, audio, talk, record, notice_ack):
    """Audio is receive-only by default; talk is staff-only (the job-owner route never asks); recording audio needs the
    recording-audio switch AND an explicit notice acknowledgement. Returns the effective ``talk``."""
    if not (audio or talk):
        return False
    require_adapters(makerspace_id, AUDIO_SWITCH)
    if "media.audio" not in binding.capabilities or "media.stream" not in binding.capabilities:
        raise AdapterError("capability_missing", "This binding has no audio track.", status_code=409)
    if talk:
        require_adapters(makerspace_id, TALK_SWITCH)
        if "media.talk" not in binding.capabilities:
            raise AdapterError("capability_missing", "This binding cannot play audio to the device.", status_code=409)
    if record:
        require_adapters(makerspace_id, AUDIO_RECORDING_SWITCH)
        if not notice_ack:
            raise AdapterError("audio_notice_required", "Recording audio needs the notice to be acknowledged.",
                               status_code=409)
    return talk


def start_staff(actor, binding, reason, record, *, audio=False, talk=False, notice_ack=False):
    """Staff watch; ``record`` additionally needs the recording switch (404 off)."""
    authorize_staff(actor, binding.makerspace_id, binding.machine, child=RECORDING_SWITCH if record else VIDEO_SWITCH)
    return _open(actor, binding, reason, record=record, audio=audio, talk=talk, notice_ack=notice_ack)


def viewer_talk(actor, watch_id, active):
    """Push-to-talk press/release, relayed as a signal. Staff watches only; every press is audited and bounded."""
    with transaction.atomic():
        watch = viewer_watch(actor, watch_id)
        require_adapters(watch.makerspace_id, TALK_SWITCH)
        _live(watch)
        if not watch.talk:
            raise PermissionDenied(gettext("This watch has no talk channel."))
        if active:
            if watch.talk_presses >= MAX_PRESSES:
                raise AdapterError("too_many_presses", "Too many talk presses in this watch.", status_code=429)
            watch.talk_presses += 1
            watch.save(update_fields=["talk_presses"])
        n = _append(watch, "viewer", {"kind": "ptt_on" if active else "ptt_off"})
        audit.record(actor, "devices.adapter_talk_started" if active else "devices.adapter_talk_stopped",
                     makerspace=watch.makerspace, target=watch.binding.device,
                     meta={"device_id": str(watch.binding.device_id), "watch_id": str(watch.pk),
                           "press": watch.talk_presses})
    return {"n": n, "active": bool(active)}


# --- snapshot fallback (only while watching) and latest-frame cache ---------------------------------------------
def store_frame(principal, watch_id, body):
    check(FRAME, body, label="frame")
    if len(body["data"]) > MAX_FRAME_CHARS:
        raise AdapterError("frame_too_large", "The frame is too large.", status_code=413)
    with transaction.atomic():
        watch = _adapter_watch(principal, watch_id)
        _live(watch)
        cache.set(f"adapter-frame:{watch.pk}", body["data"], FRAME_SECONDS)
    return {"stored": True}


def latest_frame(actor, watch_id):
    with transaction.atomic():
        watch = viewer_watch(actor, watch_id)
        _live(watch)
    data = cache.get(f"adapter-frame:{watch.pk}")
    return {"content_type": "image/jpeg", "data": data} if data else {"content_type": None, "data": None}


# --- opt-in recording: services_adapter_recording (re-exported so existing imports keep resolving) ----------------
from apps.devices.services_adapter_recording import (  # noqa: E402
    due_recordings, purge_recordings, recording_upload,
)
