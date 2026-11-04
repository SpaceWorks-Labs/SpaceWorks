"""Stable decision adapter; approval and welcome share one owner intent."""
from .notifications_p2_members import notify_member, notify_request


def notify_membership_decision(row, event):
    if hasattr(row, "state"):
        return notify_request(row, event)
    return notify_member(row, event)
