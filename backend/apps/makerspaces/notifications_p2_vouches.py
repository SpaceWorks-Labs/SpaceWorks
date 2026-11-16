"""Vouch notices carry private navigation, not voucher identities."""
from django.utils.translation import gettext
from django.utils import timezone

from apps.integrations.notification_links import local_link
from apps.integrations.notification_sources import NotificationSource, register_source
from apps.operations.notifications_p2 import body, fanout, revision, safe_notification, scoped
from .models import MembershipVouch

SOURCE = "membership.vouch"


def load(envelope):
    return scoped(MembershipVouch, envelope.makerspace_id).select_related(
        "makerspace", "request__user", "voucher",
    ).filter(pk=envelope.source_id).first()


def eligible(envelope):
    from .membership_admission_settings import settings_for, vouching_on
    from .membership_vouching import valid_vouches
    row = load(envelope)
    if row is None or envelope.event != "vouched" or row.expires_at <= timezone.now():
        return False
    if envelope.audience != "staff" and row.request.user_id != envelope.recipient_id:
        return False
    policy = settings_for(row.makerspace)
    return bool(vouching_on(row.makerspace, policy)
        and row.request.state in {"requested", "awaiting_vouches", "awaiting_payment", "active"}
        and valid_vouches(row.request, policy).filter(pk=row.pk).exists()
        and envelope.revision == revision(row.pk, row.created_at))


def content(row, audience):
    text = (gettext("A vouch was recorded for membership application #%(id)s.") % {"id": row.request_id}
            if audience == "staff"
            else gettext("A vouch was recorded for your membership application at %(space)s.")
            % {"space": row.makerspace.name})
    return body(gettext("Membership application update"), text, local_link(row.makerspace, "member"))


def render(envelope):
    return content(load(envelope), envelope.audience)


@safe_notification
def notify_vouch(row):
    return fanout(row=row, space=row.makerspace, feature="members", stream="membership", event="vouched",
        source_kind=SOURCE, revision=revision(row.pk, row.created_at), owner=row.request.user,
        owner_body=lambda: content(row, "requester"), staff_body=lambda: content(row, "staff"))


def register():
    register_source(SOURCE, NotificationSource(eligible, render))
