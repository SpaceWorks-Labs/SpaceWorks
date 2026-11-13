"""locate.calibrate / locate.indicate: a shelf pointer shown where things are, staff only.

Poses are device-specific coordinates a staff member saved per storage location, item or box. They are never on a
public or member surface (INVARIANTS: public inventory never exposes a storage location or box), are not part of any
export or tenant dump, and the commands carry the pose only to the adapter that owns the binding. Every write is
audited with the staff actor and never echoes the pose.
"""
import json
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.audit import services as audit
from apps.devices.adapter_access import scoped_binding
from apps.devices.models import AdapterEvent, AdapterPose
from apps.devices.services_adapter_commands import enqueue
from apps.devices.services_adapter_core import AdapterError
from apps.devices.services_adapter_locate_safety import indicate_params, safe_pose
from apps.devices.adapters.caps.locate_poses import KIND, POSE_KINDS
from apps.devices.adapters.schema import errors as schema_errors

MAX_POSE_BYTES = 2048
POSITION_FRESH_SECONDS = 300
LOCATE_TARGETS = ("storage_location", "item", "box")


def _binding(actor, binding_id, capability):
    binding = scoped_binding(actor, binding_id)  # foreign and missing are the same 404 (L-A6)
    if capability not in binding.capabilities:
        raise AdapterError("capability_missing", "This binding does not serve that capability.", status_code=409)
    return binding


def _target_exists(makerspace_id, target_type, target_id):
    from apps.boxes.models import Box
    from apps.inventory.models import InventoryProduct
    if target_type == "storage_location":
        return InventoryProduct.objects.filter(makerspace_id=makerspace_id, storage_location=target_id).exists()
    if not str(target_id).isdigit():
        return False
    model = Box if target_type == "box" else InventoryProduct
    return model.objects.filter(pk=int(target_id), makerspace_id=makerspace_id).exists()


def _valid_target(binding, target_type, target_id):
    if target_type not in LOCATE_TARGETS or not _target_exists(binding.makerspace_id, target_type, str(target_id)):
        raise NotFound()  # a cross-tenant or unknown target is a 404, never a hint


def _valid_pose(pose):
    if not isinstance(pose, dict) or not pose or len(json.dumps(pose)) > MAX_POSE_BYTES:
        raise AdapterError("invalid_pose", "A pose is a small non-empty JSON object.")
    for value in pose.values():
        if not isinstance(value, (int, float, str, bool)) or isinstance(value, float) and value != value:
            raise AdapterError("invalid_pose", "Pose values are numbers, strings or booleans.")
    kind = pose.get(KIND)
    if kind is not None and (kind not in POSE_KINDS or schema_errors(POSE_KINDS[kind], pose)):
        raise AdapterError("invalid_pose", "That pose does not match its published kind (docs/device-adapters/schemas).")


def save_pose(actor, binding_id, target_type, target_id, pose, note=""):
    binding = _binding(actor, binding_id, "locate.calibrate")
    _valid_target(binding, target_type, target_id)
    _valid_pose(pose)
    with transaction.atomic():
        row, created = AdapterPose.objects.update_or_create(
            binding=binding, target_type=target_type, target_id=str(target_id),
            defaults={"makerspace_id": binding.makerspace_id, "pose": pose, "note": note[:80], "saved_by": actor,
                      "updated_at": timezone.now()})
        audit.record(actor, "devices.adapter_pose_saved", makerspace=binding.makerspace, target=binding.device, meta={
            "device_id": str(binding.device_id), "binding_id": str(binding.pk), "target_type": target_type,
            "created": created})
    return row


def clear_pose(actor, binding_id, target_type, target_id):
    binding = _binding(actor, binding_id, "locate.calibrate")
    with transaction.atomic():
        deleted, _ = AdapterPose.objects.filter(binding=binding, target_type=target_type,
                                                target_id=str(target_id)).delete()
        if not deleted:
            raise NotFound()
        audit.record(actor, "devices.adapter_pose_cleared", makerspace=binding.makerspace, target=binding.device,
                     meta={"device_id": str(binding.device_id), "binding_id": str(binding.pk),
                           "target_type": target_type})


def list_poses(actor, binding_id):
    binding = _binding(actor, binding_id, "locate.calibrate")
    return list(AdapterPose.objects.filter(binding=binding).order_by("target_type", "target_id"))


def aim(actor, binding_id, pose):
    """Calibration: move the pointer to a candidate pose (nothing is saved until ``save_pose``)."""
    _valid_pose(pose)
    binding = _binding(actor, binding_id, "locate.calibrate")
    return enqueue(actor, binding_id, "locate.calibrate", "aim", {"pose": safe_pose(binding, pose)})


def jog(actor, binding_id, dx=0, dy=0):
    return enqueue(actor, binding_id, "locate.calibrate", "jog", {"dx": dx, "dy": dy})


def latest_position(actor, binding_id):
    """The newest position the pointer reported during calibration (fresh within five minutes), else None."""
    binding = _binding(actor, binding_id, "locate.calibrate")
    cutoff = timezone.now() - timedelta(seconds=POSITION_FRESH_SECONDS)
    event = AdapterEvent.objects.filter(binding=binding, event_type="calibration.position",
                                        received_at__gte=cutoff).order_by("-received_at").first()
    return event.data.get("pose") if event else None


def indicate(actor, binding_id, target_type, target_id, *, mode="point", duration_seconds=10, color=""):
    """Point at (or light) a saved target. ``clear`` needs no target and is never capped; point/light need a saved
    pose and are clamped to the binding's ``laser_max_power_pct`` / ``max_on_seconds``."""
    if mode == "clear":
        return enqueue(actor, binding_id, "locate.indicate", "indicate", indicate_params(None, None, "clear", 0))
    binding = _binding(actor, binding_id, "locate.indicate")
    _valid_target(binding, target_type, target_id)
    pose = AdapterPose.objects.filter(binding=binding, target_type=target_type, target_id=str(target_id)).first()
    if pose is None:
        raise AdapterError("pose_not_calibrated", "Calibrate this location first.", status_code=409)
    return enqueue(actor, binding_id, "locate.indicate", "indicate",
                   indicate_params(binding, pose.pose, mode, duration_seconds, color))
