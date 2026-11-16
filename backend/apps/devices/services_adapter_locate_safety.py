"""Server-enforced laser limits for shelf pointers (decision 331 addendum).

The adapter only obeys; these caps live in the binding config (``laser_max_power_pct``, ``max_on_seconds``) and are
applied to every ``indicate`` and ``aim`` command the server builds, whoever asked (staff console, "show on shelf",
kiosk scan). A pose of a laser kind (``pan_tilt``, ``galvo_xy``) is always bounded: with no configured on-time cap the
default below applies, and with a configured power cap an unset ``laser_power_pct`` is raised to the cap's ceiling
(never above). ``clear`` is NEVER capped, delayed or rate-limited: switching a laser off must always get through.
"""
from apps.devices.adapters.caps.locate_poses import KIND, LASER_KINDS
from apps.devices.services_adapter_safety import own_config

DEFAULT_LASER_MAX_ON_SECONDS = 60


def limits(binding):
    config = own_config(binding)
    return config.get("laser_max_power_pct"), config.get("max_on_seconds")


def _is_laser(pose):
    return isinstance(pose, dict) and pose.get(KIND) in LASER_KINDS


def safe_pose(binding, pose):
    """The pose with ``laser_power_pct`` held at or below the binding's cap (a copy; the saved pose is untouched)."""
    max_power, _ = limits(binding)
    if max_power is None or not _is_laser(pose):
        return pose
    return {**pose, "laser_power_pct": min(pose.get("laser_power_pct", max_power), max_power)}


def safe_duration(binding, pose, duration_seconds):
    """``duration_seconds`` held at or below ``max_on_seconds`` (or the laser default when none is configured)."""
    _, max_on = limits(binding)
    if max_on is None and _is_laser(pose):
        max_on = DEFAULT_LASER_MAX_ON_SECONDS
    return duration_seconds if max_on is None else min(duration_seconds, max_on)


def indicate_params(binding, pose, mode, duration_seconds, color=""):
    """The command params for a point/light request, with both caps applied; ``clear`` params carry nothing else."""
    if mode == "clear":
        return {"mode": "clear"}
    params = {"mode": mode, "pose": safe_pose(binding, pose),
              "duration_seconds": safe_duration(binding, pose, duration_seconds)}
    if color:
        params["color"] = color
    return params
