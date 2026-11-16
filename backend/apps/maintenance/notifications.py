"""Compatibility barrel for source-backed maintenance notifications."""
from apps.machines.notifications_p2_maintenance import notify as notify_maintenance_lifecycle

__all__ = ["notify_maintenance_lifecycle"]
