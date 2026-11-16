"""detection.report admission and diagnostics (decision 321c, e).

A detection is the append-only ``AdapterEvent`` ``detection.reported``; it notifies staff and the job owner through the
catalogue (``adapter_notifications``) and NEVER acts: pausing, powering off or cancelling is a staff decision or the
adapter's own business (decision 320). Admission is rate limited per binding so a stuck model cannot flood the table.
"""
from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone

from apps.devices.adapter_access import DETECTIONS_SWITCH, scoped_binding
from apps.devices.models import AdapterArtifact, AdapterEvent, AdapterProfile
from apps.devices.services_adapter_core import AdapterError

RATE_LIMIT = 30  # stored detections per binding per window
RATE_WINDOW = 600


def admit(binding, data):
    """Raise 429 ``rate_limited`` past the window cap; refuse an evidence frame that is not this binding's artifact."""
    if binding is None:
        raise AdapterError("binding_required", "A detection must name the binding it was seen on.")
    artifact_id = data.get("artifact_id")
    if artifact_id and not AdapterArtifact.objects.filter(pk=artifact_id, binding=binding).exists():
        raise AdapterError("invalid_artifact", "The evidence frame is not an artifact of this binding.")
    key = f"adapter-detect-rate:{binding.pk}"
    cache.add(key, 0, RATE_WINDOW)
    try:
        used = cache.incr(key)
    except ValueError:
        used = 1
    if used > RATE_LIMIT:
        raise AdapterError("rate_limited", "Too many detections; slow down.", status_code=429)


def staff_list(actor, binding_id, params):
    binding = scoped_binding(actor, binding_id, child=DETECTIONS_SWITCH)
    queryset = AdapterEvent.objects.filter(binding=binding, event_type="detection.reported")
    if params.get("kind"):
        queryset = queryset.filter(data__kind=params["kind"])
    return queryset


def run_window(request):
    """(start, end) of the job's own run on its machine, or None when it never started.

    A detection carries no job link, so the window IS the authorisation boundary: from the second the job
    started to the second it reached a terminal state (completed, failed or cancelled). ``end`` is None while
    it still runs. Detections are stamped in whole seconds, so both bounds are whole seconds too.
    """
    if request.started_at is None:
        return None
    start = request.started_at.replace(microsecond=0)
    ends = [at for at in (request.completed_at, request.failed_at, request.cancelled_at) if at is not None]
    end = min(ends).replace(microsecond=0) + timedelta(seconds=1) if ends else None
    return start, end


def owner_list(actor, request_id):
    """Detections on the machine of the owner's own job, during that job's run only (never a later job's)."""
    from rest_framework.exceptions import NotFound
    from apps.devices.adapter_access import require_adapters
    from apps.devices.models import AdapterBinding
    from apps.machines.models import MachineServiceRequest
    request = MachineServiceRequest.objects.filter(pk=request_id).first()
    if request is None or (request.member_id or request.requester_id) != actor.pk or not request.assigned_machine_id:
        raise NotFound()
    require_adapters(request.makerspace_id, DETECTIONS_SWITCH)
    window = run_window(request)
    if window is None:
        return AdapterEvent.objects.none()
    start, end = window
    binding_ids = AdapterBinding.objects.filter(makerspace_id=request.makerspace_id,
                                                machine_id=request.assigned_machine_id).values("pk")
    queryset = AdapterEvent.objects.filter(binding_id__in=binding_ids, event_type="detection.reported",
                                           observed_at__gte=start)
    return queryset.filter(observed_at__lt=end) if end is not None else queryset


def record_health(device, diagnostics):
    """Adapter health/firmware from a status item's ``diagnostics`` block (advisory)."""
    updates = {"health_at": timezone.now()}
    if diagnostics.get("health"):
        updates["health"] = diagnostics["health"]
    if diagnostics.get("firmware"):
        updates["firmware"] = diagnostics["firmware"]
    AdapterProfile.objects.filter(device=device).update(**updates)
