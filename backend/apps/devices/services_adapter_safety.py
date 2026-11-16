"""Server-enforced safety (decision 311/312): area-clear gate, idle auto-off, session-ending notice.

The adapter only REPORTS (``status`` and ``safety.area_cleared``); the rules live in ``AdapterBinding.config``
(``caps/safety.py`` CONFIG) and are enforced here: in the access decision and the job lease (``area_blocked``) and
by a periodic sweep (``sweep_safety``) that powers an idle machine off through the ordinary control command queue.
A sweep problem in one binding never stops the others.
"""
import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.devices.adapters.caps.safety import CONFIG, PROFILE
from apps.devices.adapters.schema import errors
from apps.devices.models import AdapterBinding, AdapterCommand, AdapterStatus

logger = logging.getLogger(__name__)
ENDING_SOON_SECONDS = 300
OFF_COOLDOWN_SECONDS = 600


def own_config(binding):
    """The binding's own overrides, or an empty config if it was never set or is not valid."""
    config = binding.config if isinstance(binding.config, dict) else {}
    return {} if errors(CONFIG, config) else config


def type_defaults(binding):
    """The safety profile of the binding's machine type (decision 311a), or {}."""
    from apps.devices.models import AdapterTypeProfile
    if binding.machine_id is None:
        return {}
    row = AdapterTypeProfile.objects.filter(
        makerspace_id=binding.makerspace_id, machine_type_id=binding.machine.machine_type_id).first()
    config = row.config if row and isinstance(row.config, dict) else {}
    return {} if errors(PROFILE, config) else config


def config_of(binding):
    """Effective config: the machine type's profile with the binding's own overrides on top."""
    return {**type_defaults(binding), **own_config(binding)}


def config_view(binding):
    """Console read-back: the binding's own overrides plus every effective key with where it comes from."""
    own = own_config(binding)
    effective = {key: {"value": value, "source": "type"} for key, value in type_defaults(binding).items()}
    effective.update({key: {"value": value, "source": "binding"} for key, value in own.items()})
    return {"config": own, "effective_config": effective}


def area_blocked(binding):
    """True when the binding demands an area-clear confirmation (or the adapter reported not-clear) and has none."""
    if "safety" not in binding.capabilities:
        return False
    status = AdapterStatus.objects.filter(binding=binding).first()
    clear = status.payload.get("area_clear") if status is not None else None
    if clear is False:
        return True
    return bool(config_of(binding).get("require_area_clear")) and clear is not True


def clear_area_marker(binding):
    """A job lease or session start consumes the confirmation: the next one needs a fresh ``safety.area_cleared``."""
    status = AdapterStatus.objects.select_for_update().filter(binding=binding).first()
    if status is not None and config_of(binding).get("require_area_clear") and status.payload.get("area_clear"):
        status.payload = {**status.payload, "area_clear": False}
        status.save(update_fields=["payload"])


def track_idle(previous, state, observed):
    """The ``idle_since`` stamp the status store keeps: when the current unbroken idle stretch began (else None)."""
    if state != "idle":
        return None
    if previous is not None and previous.state == "idle" and previous.payload.get("idle_since"):
        return previous.payload["idle_since"]
    return int(observed.timestamp())


def effective_max_seconds(binding, machine):
    """The session length cap: the shorter of the machine policy and the adapter config (type profile + override)."""
    from apps.devices.services_adapter_access import policy_max_seconds
    policy = policy_max_seconds(machine)
    own = config_of(binding).get("max_session_minutes")
    return min(policy, own * 60) if own else policy


def _already_off(binding, now):
    return AdapterCommand.objects.filter(
        binding=binding, capability="control", command="power", created_at__gte=now - timedelta(seconds=OFF_COOLDOWN_SECONDS),
        params__on=False).exists()


def _member_present(binding):
    from apps.machines.models import MachineSession
    return binding.machine_id is not None and MachineSession.objects.filter(
        machine_id=binding.machine_id, ended_at__isnull=True).exists()


def power_off_if_idle(binding, now):
    """Queue ``control power off`` for an idle, unattended machine whose idle stretch exceeded the configured minutes."""
    minutes = config_of(binding).get("auto_off_idle_minutes")
    if not minutes or "control" not in binding.capabilities or binding.status.state != "idle":
        return False
    since = binding.status.payload.get("idle_since")
    if since is None or now.timestamp() - since < minutes * 60 or binding.status.payload.get("power") == "off":
        return False
    if _already_off(binding, now) or _member_present(binding):
        return False
    return queue_power_off(binding, now, reason="idle", idle_minutes=int((now.timestamp() - since) // 60))


def queue_power_off(binding, now, *, reason, **meta):
    """Queue ``control power off`` on the binding's own queue (system action, no staff actor) and audit it."""
    if "control" not in binding.capabilities or _already_off(binding, now):
        return False
    row = AdapterCommand.objects.create(
        makerspace_id=binding.makerspace_id, device=binding.device, binding=binding,
        device_key_version=binding.device.key_version, capability="control", command="power", params={"on": False},
        expires_at=now + timedelta(seconds=600))
    audit.record(None, "devices.adapter_auto_off", makerspace=binding.makerspace, target=binding.device, meta={
        "device_id": str(binding.device_id), "binding_id": str(binding.pk), "command_id": str(row.pk),
        "reason": reason, **meta})
    from apps.devices.services_adapter_webhook import wake
    wake(binding.device, "command.queued", binding_id=binding.pk, capability="control", command="power")
    return True


def enforce_session_limits(binding, now):
    """(ended, notified): warn at T-5 minutes, then end a session past the cap and queue power off (like idle).

    The cap is ``effective_max_seconds``. Only an adapter-configured cap (type profile or binding) is enforced here;
    the machine policy's own maximum keeps being the session service's job.
    """
    from apps.devices.adapter_notifications import notify_session_ending
    from apps.machines.models import MachineSession
    from apps.machines.sessions_rules import SessionRefused
    from apps.machines.sessions_service import stop
    if binding.machine_id is None:
        return 0, 0
    ended = notified = 0
    configured = bool(config_of(binding).get("max_session_minutes"))
    for session in MachineSession.objects.select_related("machine__makerspace", "machine__machine_type", "member").filter(
            machine_id=binding.machine_id, ended_at__isnull=True):
        remaining = session.started_at + timedelta(seconds=effective_max_seconds(binding, session.machine)) - now
        if remaining <= timedelta(0):
            if not configured:
                continue
            try:
                stop(session, actor=None, reason=MachineSession.StopReason.MAX_LENGTH, at=now)
            except SessionRefused:
                continue
            queue_power_off(binding, now, reason="max_session", session_id=session.pk)
            ended += 1
        elif remaining <= timedelta(seconds=ENDING_SOON_SECONDS):
            notified += bool(notify_session_ending(binding, session, int(remaining.total_seconds() // 60) + 1))
    return ended, notified


def sweep_safety(*, now=None):
    """Periodic server-side safety pass. Returns counters; each binding is isolated from the others' failures."""
    from apps.devices.adapter_access import adapters_enabled
    from apps.tenant_migration.gate_runtime import fanout_tenant_write
    now = now or timezone.now()
    counts = {"auto_off": 0, "ending_soon": 0, "session_ended": 0, "skipped": 0}
    space_ids = AdapterBinding.objects.filter(enabled=True, status__isnull=False).values_list(
        "makerspace_id", flat=True).distinct().order_by("makerspace_id")
    for space_id in space_ids:
        if not adapters_enabled(space_id):
            continue
        with fanout_tenant_write(space_id, operation="devices.adapter_safety", counts=counts) as should_process:
            if not should_process:
                continue
            bindings = AdapterBinding.objects.select_related("device", "status", "machine", "makerspace").filter(
                makerspace_id=space_id, enabled=True, status__isnull=False, device__status="active")
            for binding in bindings:
                try:
                    with transaction.atomic():
                        counts["auto_off"] += power_off_if_idle(binding, now)
                        ended, warned = enforce_session_limits(binding, now)
                        counts["session_ended"] += ended
                        counts["ending_soon"] += warned
                except Exception:  # noqa: BLE001 - one binding's problem must not stop the sweep
                    logger.warning("adapter safety sweep failed", extra={"binding_id": str(binding.pk)}, exc_info=True)
    return counts
