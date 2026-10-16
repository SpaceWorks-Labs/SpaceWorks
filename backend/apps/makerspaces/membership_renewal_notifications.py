"""Stable renewal entry points."""
from .notifications_p2_terms import notify_term
from .notifications_p2_members import notify_member


def notify_membership(membership, event):
    return notify_member(membership, event, staff=False)
