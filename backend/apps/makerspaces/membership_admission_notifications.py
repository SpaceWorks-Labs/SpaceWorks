"""Applicant and authorized staff envelopes from the live admission row."""
from .notifications_p2_members import notify_request


def notify_admission(row, event):
    return notify_request(row, event)
