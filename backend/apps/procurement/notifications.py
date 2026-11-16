"""Compatibility barrel for source-backed procurement notifications."""
from apps.machines.notifications_p2_stock import notify as notify_stock

__all__ = ["notify_stock"]
