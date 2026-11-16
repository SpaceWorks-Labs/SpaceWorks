"""Stable membership notification entry points."""
from .notifications_p2_members import notify_member, notify_request


def send_member_welcome(membership, *, source):
    return notify_member(membership, "approved" if source == "approval" else "joined", staff=False)


def send_member_verified(membership):
    return notify_member(membership, "verified", staff=False)


def notify_membership_request_pending(request, *, sync=False):
    return notify_request(request, "request_pending")


def notify_member_joined(membership, *, sync=False):
    # Activation already reserved the owner's one welcome intent.
    return notify_member(membership, "member_joined", owner=False)
