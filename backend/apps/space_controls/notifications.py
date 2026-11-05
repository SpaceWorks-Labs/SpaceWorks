"""Platform mail to a space's Space Managers about superadmin controls (#185).

Platform mail (``makerspace=None``, platform connection), so a paused space's own
``email`` module and its suspended source gate can never mute it -- exactly like the
archive-request outcome mail. Sends run after commit, are caught and logged, and never
roll back a control. The superadmin's private reason for a suspension is never mailed.
"""

import logging

from django.db import transaction

from apps.integrations.dispatch import dispatch_email

logger = logging.getLogger(__name__)

SPACE_MANAGER = "space_manager"


def manager_rows(makerspace_id):
    from apps.makerspaces.models import MakerspaceMembership

    return (
        MakerspaceMembership.staff_tracks.filter(
            makerspace_id=makerspace_id, status="active", assigned_role__slug=SPACE_MANAGER,
            user__is_active=True, user__access_status="active",
        )
        .select_related("user")
        .order_by("pk")
    )


def manager_emails(makerspace_id):
    emails = []
    for row in manager_rows(makerspace_id):
        email = (row.user.email or "").strip()
        if email and email not in emails:
            emails.append(email)
    return emails


def send_to_managers(makerspace_id, *, subject, body, event):
    """Mail every active Space Manager now; returns how many messages were attempted."""
    sent = 0
    for email in manager_emails(makerspace_id):
        try:
            dispatch_email(
                to_email=email, subject=subject, text_body=body, makerspace=None,
                connection="platform", stream="governance", event=event, audience="space_manager",
                persist_body=False, sync=True,
            )
            sent += 1
        except Exception:
            logger.warning("space_control_mail_failed", extra={"makerspace_id": makerspace_id, "event": event})
    return sent


def schedule_manager_mail(makerspace_id, *, subject, body, event):
    transaction.on_commit(lambda: send_to_managers(makerspace_id, subject=subject, body=body, event=event))


MESSAGES = {
    "suspended": (
        "{name} has been paused",
        "The platform operator has paused {name} on Space Works.\n\n"
        "While it is paused, staff and members see a \"This space is paused\" page, the public pages are "
        "offline, scheduled jobs and outbound messages stop, and nothing is deleted. Contact the platform "
        "operator to restore it.",
    ),
    "unsuspended": (
        "{name} is available again",
        "The platform operator has restored {name} on Space Works. Everything works as before.",
    ),
    "read_only": (
        "{name} is now read-only",
        "{name} is now read-only on Space Works.\n\nEveryone can still view and export, but nothing new can "
        "be created (no loans, bookings, jobs, sign-ups or payments).\n\nReason: {reason}",
    ),
    "read_only_lifted": (
        "{name} can be used normally again",
        "Read-only mode has ended for {name} on Space Works. Everything can be created and changed again.",
    ),
}


def notify(makerspace, kind, *, reason=""):
    subject, body = MESSAGES[kind]
    values = {"name": makerspace.name, "reason": reason}
    schedule_manager_mail(
        makerspace.pk, subject=subject.format(**values), body=body.format(**values),
        event=f"space_control_{kind}",
    )
