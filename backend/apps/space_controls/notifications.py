"""Platform mail to a space's Space Managers about superadmin controls (#185).

Platform mail (``makerspace=None``, platform connection), so a paused space's own
``email`` module and its suspended source gate can never mute it -- exactly like the
archive-request outcome mail. Sends run after commit, are caught and logged, and never
roll back a control. The superadmin's private reason for a suspension is never mailed.
"""

import logging

from django.db import transaction
from django.utils.translation import gettext, gettext_noop

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
    """Mail every active Space Manager now; returns how many messages were attempted.

    ``subject`` and ``body`` are text or zero-argument callables; callables run once per manager
    inside that manager's locale so each person reads their own language.
    """
    from config.locale_resolution import override_for

    sent, seen = 0, set()
    for row in manager_rows(makerspace_id):
        email = (row.user.email or "").strip()
        if not email or email in seen:
            continue
        seen.add(email)
        try:
            with override_for(user=row.user, makerspace=row.makerspace):
                text_subject = str(subject() if callable(subject) else subject)
                text_body = str(body() if callable(body) else body)
            dispatch_email(
                to_email=email, subject=text_subject, text_body=text_body, makerspace=None,
                connection="platform", stream="governance", event=event, audience="space_manager",
                persist_body=False, sync=True,
            )
            sent += 1
        except Exception:
            logger.warning("space_control_mail_failed", extra={"makerspace_id": makerspace_id, "event": event})
    return sent


def schedule_manager_mail(makerspace_id, *, subject, body, event):
    transaction.on_commit(lambda: send_to_managers(makerspace_id, subject=subject, body=body, event=event))


# gettext_noop marks the text for extraction; notify() translates it per manager.
MESSAGES = {
    "suspended": (
        gettext_noop("{name} has been paused"),
        gettext_noop(
            "The platform operator has paused {name} on Space Works.\n\n"
            "While it is paused, staff and members see a \"This space is paused\" page, the public pages are "
            "offline, scheduled jobs and outbound messages stop, and nothing is deleted. Contact the platform "
            "operator to restore it."
        ),
    ),
    "unsuspended": (
        gettext_noop("{name} is available again"),
        gettext_noop("The platform operator has restored {name} on Space Works. Everything works as before."),
    ),
    "read_only": (
        gettext_noop("{name} is now read-only"),
        gettext_noop(
            "{name} is now read-only on Space Works.\n\nEveryone can still view and export, but nothing new can "
            "be created (no loans, bookings, jobs, sign-ups or payments).\n\nReason: {reason}"
        ),
    ),
    "read_only_lifted": (
        gettext_noop("{name} can be used normally again"),
        gettext_noop("Read-only mode has ended for {name} on Space Works. Everything can be created and changed again."),
    ),
}


def notify(makerspace, kind, *, reason=""):
    subject, body = MESSAGES[kind]
    values = {"name": makerspace.name, "reason": reason}
    schedule_manager_mail(
        makerspace.pk, subject=lambda: gettext(subject).format(**values), body=lambda: gettext(body).format(**values),
        event=f"space_control_{kind}",
    )
