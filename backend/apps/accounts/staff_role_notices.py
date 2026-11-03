""""You were granted a staff role": a private notice to the person (in-app + email).

Sent after a grant, a restore and an accepted staff invitation commit, through the
personal envelope pipeline (the person's own channel choices; stream ``account``). The
live source check re-reads the staff row at send time, so a notice for a row revoked in
the meantime is dropped. Delivery failures never touch the role change.
"""

import logging

from django.db import transaction

logger = logging.getLogger(__name__)
SOURCE = "accounts.staff_role"
EVENT = "staff_role_granted"


def _row(envelope):
    from apps.makerspaces.models import MakerspaceMembership
    return MakerspaceMembership.staff_tracks.select_related("user", "makerspace").filter(
        pk=envelope.source_id, makerspace_id=envelope.makerspace_id, user_id=envelope.recipient_id).first()


def eligible(envelope):
    from apps.accounts.staff_identity import is_person
    from apps.makerspaces.servability import is_servable

    row = _row(envelope) if envelope.event == EVENT else None
    return bool(row is not None and row.status == "active" and is_servable(row.makerspace)
                and is_person(row.user) and row.user.is_active and row.user.access_status == "active"
                and not row.user.is_tenant_dump_stub)


def _emit(row):
    from apps.accounts.staff_account_policy import role_keys
    from apps.integrations.notification_outbox import emit
    from apps.makerspaces.models import MakerspaceRole

    names = dict(MakerspaceRole.objects.filter(makerspace_id=row.makerspace_id).values_list("slug", "name"))
    roles = ", ".join(names.get(slug, slug) for slug in role_keys(row))
    space = row.makerspace
    revision = str(int(row.activated_at.timestamp())) if row.activated_at else "1"
    try:
        with transaction.atomic():
            emit(makerspace=space, recipient=row.user, feature="members", stream="account", event=EVENT,
                 audience="member", source_kind=SOURCE, source_id=str(row.pk), revision=revision,
                 dedup_key=f"staff-role:{row.pk}:{revision}:{row.status}", context={"membership_id": row.pk},
                 rendered={"subject": f"You have a staff role at {space.name}",
                           "text": f"You were given the {roles} role at {space.name}. Open the staff "
                                   "console from your account. Staff screens need two-step sign-in: "
                                   "set it up within three days."})
    except Exception:
        logger.warning("staff_role_notice_failed", extra={"membership_id": row.pk})


def notify_granted(row):
    """After commit; ``row`` is a staff-track membership."""
    from apps.makerspaces.models import MakerspaceMembership

    def _send():
        fresh = MakerspaceMembership.staff_tracks.select_related("user", "makerspace").filter(pk=row.pk).first()
        if fresh is not None and fresh.status == "active":
            _emit(fresh)

    transaction.on_commit(_send)


def register():
    from apps.integrations.notification_sources import NotificationSource, register_source
    register_source(SOURCE, NotificationSource(eligible))
