"""Platform announcements: a banner and an optional email to Space Managers (#185 item 6).

The banner shows to the staff of every targeted space (and to its members when
``show_to_members``) between ``starts_at`` and ``ends_at``; the superadmin sees every live
one. The email goes once, at ``starts_at``, to the active Space Managers of the targeted
servable spaces, as platform mail. Creation and cancellation are superadmin-only and
audited at platform level (no tenant: one announcement can target every space).
"""

from django.utils.translation import gettext
import logging

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit
from apps.makerspaces.lifecycle_authority import require_platform_superadmin
from apps.makerspaces.models import Makerspace
from apps.makerspaces.servability import servable_queryset

from .errors import SpaceControlConflict
from .models import PlatformAnnouncement, PlatformAnnouncementTarget

logger = logging.getLogger(__name__)
A = PlatformAnnouncement


def status(row, now=None):
    now = now or timezone.now()
    if row.cancelled_at is not None:
        return "cancelled"
    if row.starts_at > now:
        return "scheduled"
    if row.ends_at is not None and row.ends_at <= now:
        return "ended"
    return "live"


def live_q(now):
    return Q(cancelled_at__isnull=True, starts_at__lte=now) & (Q(ends_at__isnull=True) | Q(ends_at__gt=now))


def create(actor, data):
    require_platform_superadmin(actor)
    ids = sorted(set(data.get("makerspace_ids") or []))
    selected = data["audience"] == A.Audience.SELECTED_SPACES
    if selected and not ids:
        raise ValidationError({"makerspace_ids": gettext("Choose at least one space.")})
    with transaction.atomic():
        spaces = list(Makerspace.objects.filter(pk__in=ids)) if selected else []
        if len(spaces) != len(ids if selected else []):
            raise ValidationError({"makerspace_ids": gettext("Choose existing spaces.")})
        row = A.objects.create(
            title=data["title"], body=data["body"], severity=data["severity"], audience=data["audience"],
            starts_at=data.get("starts_at") or timezone.now(), ends_at=data.get("ends_at"),
            send_email=data.get("send_email", False), show_to_members=data.get("show_to_members", False),
            created_by=actor,
        )
        PlatformAnnouncementTarget.objects.bulk_create(
            [PlatformAnnouncementTarget(announcement=row, makerspace=space) for space in spaces])
        audit.record(actor, "space_control.announcement_created", makerspace=None, target=row, meta={
            "severity": row.severity, "audience": row.audience, "space_count": len(spaces),
            "send_email": row.send_email, "show_to_members": row.show_to_members,
        })
    return row


def cancel(actor, announcement_id):
    require_platform_superadmin(actor)
    with transaction.atomic():
        row = A.objects.select_for_update().get(pk=announcement_id)
        if row.cancelled_at is not None:
            raise SpaceControlConflict("announcement_cancelled", "This announcement is already cancelled.")
        row.cancelled_at, row.cancelled_by = timezone.now(), actor
        row.save(update_fields=["cancelled_at", "cancelled_by"])
        audit.record(actor, "space_control.announcement_cancelled", makerspace=None, target=row, meta={})
    return row


def target_space_ids(row):
    """Servable spaces the announcement reaches (never archived or paused ones)."""
    spaces = servable_queryset()
    if row.audience == A.Audience.SELECTED_SPACES:
        spaces = spaces.filter(pk__in=row.targets.values("makerspace_id"))
    return list(spaces.values_list("pk", flat=True))


def send_due_emails(now=None):
    """Claim each due announcement once, then mail outside the claiming transaction."""
    from .notifications import manager_emails
    from apps.integrations.dispatch import dispatch_email

    now = now or timezone.now()
    sent = 0
    due = A.objects.filter(live_q(now), send_email=True, email_sent_at__isnull=True).values_list("pk", flat=True)
    for pk in list(due[:20]):
        with transaction.atomic():
            row = A.objects.select_for_update().filter(pk=pk, email_sent_at__isnull=True).first()
            if row is None:
                continue
            row.email_sent_at = now
            row.save(update_fields=["email_sent_at"])
        emails = sorted({email for space_id in target_space_ids(row) for email in manager_emails(space_id)})
        count = 0
        for email in emails:
            try:
                dispatch_email(to_email=email, subject=gettext('Space Works: {title}').format(title=row.title), text_body=row.body,
                               makerspace=None, connection="platform", stream="governance",
                               event="platform_announcement", audience="space_manager",
                               persist_body=False, sync=True)
                count += 1
            except Exception:
                logger.warning("platform_announcement_mail_failed", extra={"announcement_id": row.pk})
        A.objects.filter(pk=row.pk).update(email_recipient_count=count)
        audit.record(None, "space_control.announcement_emailed", makerspace=None, target=row,
                     meta={"recipient_count": count})
        sent += 1
    return {"announcements": sent}
