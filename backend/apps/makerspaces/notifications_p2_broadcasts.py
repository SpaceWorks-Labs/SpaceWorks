"""Member broadcast envelopes; the persisted source and live segment grant authority."""
from apps.accounts import rbac
from apps.accounts.models import User
from apps.integrations.notification_sources import NotificationSource, register_source
from apps.operations.notifications_p2 import body, fanout, revision, safe_notification, scoped
from apps.notifications.models_broadcasts import MemberBroadcast
from .platform import feature_enabled, module_enabled

SOURCE = "membership.broadcast"
SEGMENT_KEYS = {"plan_id", "status", "certification_id"}


def load(envelope):
    return scoped(MemberBroadcast, envelope.makerspace_id).select_related(
        "makerspace", "created_by",
    ).filter(pk=envelope.source_id).first()


def broadcast_revision(row):
    # Private content is hashed, never copied into unencrypted context or audit.
    return revision(row.pk, row.created_at, row.title, row.body)


def eligible(envelope):
    from apps.notifications.broadcasts import segment_members
    row = load(envelope)
    if row is None or envelope.event != "broadcast" or envelope.audience == "staff":
        return False
    space = row.makerspace
    segment = envelope.context.get("segment", {})
    if not isinstance(segment, dict) or set(segment) - SEGMENT_KEYS:
        return False
    return bool(envelope.revision == broadcast_revision(row)
        and feature_enabled(space, "membership.broadcasts") and module_enabled(space, "membership")
        and module_enabled(space, "notifications") and row.created_by
        and rbac.can(row.created_by, rbac.Action.MANAGE_MEMBERS, space.pk)
        and segment_members(space, segment).filter(user_id=envelope.recipient_id).exists())


def render(envelope):
    row = load(envelope)
    return body(row.title, row.body, f"/m/{row.makerspace.slug}/member")


@safe_notification
def notify_broadcast(row, *, user_id, segment):
    if set(segment) - SEGMENT_KEYS:
        raise ValueError("Unknown member broadcast segment")
    user = User.objects.get(pk=user_id)
    return fanout(row=row, space=row.makerspace, feature="members", stream="membership", event="broadcast",
        source_kind=SOURCE, revision=broadcast_revision(row), owner=user,
        owner_body=body(row.title, row.body, f"/m/{row.makerspace.slug}/member"),
        staff=False, context={"segment": segment})


def register():
    register_source(SOURCE, NotificationSource(eligible, render))
