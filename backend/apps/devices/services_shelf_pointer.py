"""Staff "Show on shelf" / "Clear" and coverage for shelf pointers (decision 331a).

Staff only, and never a pose: every answer says whether a calibrated pointer covers a target and whether a light was
queued, but the coordinates only ever travel inside the command to the adapter that owns the binding. Everything is
404 while ``machines.integrations`` is off (the same typed refusal as every adapter route). The commands go through
``services_adapter_locate_safety`` so the binding's laser caps apply here exactly as they do for the console and kiosk;
``clear`` is never capped and has no rate limit.
"""
from datetime import timedelta

from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied

from apps.accounts import rbac
from apps.audit import services as audit
from apps.devices.adapter_access import require_adapters
from apps.devices.models import AdapterBinding, AdapterCommand, AdapterPose
from apps.devices.services_adapter_core import AdapterError
from apps.devices.services_adapter_locate_safety import indicate_params

Action = rbac.Action
SHOW_ACTIONS = (Action.EDIT_INVENTORY, Action.ISSUE_REQUEST, Action.ISSUE_DIRECT_LOAN, Action.MANAGE_DEVICES)
COMMAND_TTL_SECONDS = 120
MAX_COVERAGE_TARGETS = 200
TARGET_TYPES = ("storage_location", "item", "box")


def authorize(actor, makerspace_id, actions=SHOW_ACTIONS):
    """404 while the integrations switch is off, 403 for a member who is not inventory/handover/device staff."""
    require_adapters(makerspace_id)
    if not any(rbac.can(actor, action, makerspace_id) for action in actions):
        raise PermissionDenied()


def _live_poses(makerspace_id):
    return AdapterPose.objects.select_related("binding__device").filter(
        makerspace_id=makerspace_id, binding__enabled=True, binding__device__status="active",
        binding__capabilities__contains=["locate.indicate"])


def _item_locations(makerspace_id, item_ids):
    from apps.inventory.models import InventoryProduct
    return dict(InventoryProduct.objects.filter(makerspace_id=makerspace_id, pk__in=item_ids).exclude(
        storage_location="").values_list("pk", "storage_location"))


def _resolve(makerspace_id, targets):
    """``{(type, id): AdapterPose or None}``: an exact pose, else (for an item) the pose of its storage location."""
    poses = {(row.target_type, row.target_id): row for row in _live_poses(makerspace_id)}
    item_ids = [int(i) for t, i in targets if t == "item" and str(i).isdigit()]
    where = _item_locations(makerspace_id, item_ids) if item_ids and poses else {}
    out = {}
    for target_type, target_id in targets:
        row = poses.get((target_type, target_id))
        if row is None and target_type == "item" and str(target_id).isdigit():
            row = poses.get(("storage_location", where.get(int(target_id), "")))
        out[(target_type, target_id)] = row
    return out


def _clean_targets(targets):
    if len(targets) > MAX_COVERAGE_TARGETS:
        raise AdapterError("too_many_targets", "Ask about at most 200 targets at a time.")
    return [(t["target_type"], str(t["target_id"])) for t in targets]


def coverage(actor, makerspace_id, targets):
    """Which of these targets a calibrated, active pointer can light. Never returns a pose."""
    authorize(actor, makerspace_id)
    keys = _clean_targets(targets)
    found = _resolve(makerspace_id, keys)
    return [{"target_type": t, "target_id": i, "covered": found[(t, i)] is not None} for t, i in keys]


def _queue(makerspace, binding, params, actor, action, meta):
    row = AdapterCommand.objects.create(
        makerspace=makerspace, device=binding.device, binding=binding, device_key_version=binding.device.key_version,
        capability="locate.indicate", command="indicate", params=params, created_by=actor,
        expires_at=timezone.now() + timedelta(seconds=COMMAND_TTL_SECONDS))
    audit.record(actor, action, makerspace=makerspace, target=binding.device, meta={
        "device_id": str(binding.device_id), "binding_id": str(binding.pk), "command_id": str(row.pk), **meta})
    from apps.devices.services_adapter_webhook import wake
    wake(binding.device, "command.queued", binding_id=binding.pk, capability="locate.indicate", command="indicate")
    return row


def point_at(makerspace, pose_row, *, actor, duration_seconds, mode="point", color="", action="devices.adapter_shelf_shown"):
    """Queue one point/light command on the pose's own binding with the laser caps applied. Returns the command."""
    binding = pose_row.binding
    params = indicate_params(binding, pose_row.pose, mode, duration_seconds, color)
    meta = {"target_type": pose_row.target_type, "mode": mode,
            "clamped": params["duration_seconds"] != duration_seconds or params["pose"] != pose_row.pose}
    return _queue(makerspace, binding, params, actor, action, meta)


def show(actor, makerspace_id, target_type, target_id, *, mode="point", duration_seconds=15, color=""):
    authorize(actor, makerspace_id)
    from apps.makerspaces.models import Makerspace
    makerspace = Makerspace.objects.filter(pk=makerspace_id).first()
    key = (target_type, str(target_id))
    row = _resolve(makerspace_id, [key])[key]
    if row is None or makerspace is None:
        raise NotFound()
    return point_at(makerspace, row, actor=actor, duration_seconds=duration_seconds, mode=mode, color=color)


def clear(actor, makerspace_id, target_type="", target_id=""):
    """Switch off: the pointer covering the target, or every active pointer in the space. Always allowed."""
    authorize(actor, makerspace_id)
    from apps.makerspaces.models import Makerspace
    makerspace = Makerspace.objects.filter(pk=makerspace_id).first()
    if target_type:
        row = _resolve(makerspace_id, [(target_type, str(target_id))])[(target_type, str(target_id))]
        bindings = [row.binding] if row else []
    else:
        bindings = list(AdapterBinding.objects.select_related("device").filter(
            makerspace_id=makerspace_id, enabled=True, device__status="active",
            capabilities__contains=["locate.indicate"]))
    return [_queue(makerspace, b, indicate_params(b, None, "clear", 0), actor, "devices.adapter_shelf_cleared", {})
            for b in bindings]
