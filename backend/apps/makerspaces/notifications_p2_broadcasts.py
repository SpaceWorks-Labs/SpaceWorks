"""Member broadcast envelopes; the persisted source and live segment grant authority."""
from django.db.models import Q
from rest_framework.exceptions import ValidationError

from apps.integrations.notification_links import local_link
from apps.accounts import rbac
from apps.accounts.models import User
from apps.integrations.notification_sources import NotificationSource, register_source
from apps.operations.notifications_p2 import body, fanout, revision, scoped
from apps.notifications.models_broadcasts import MemberBroadcast
from .platform import feature_enabled, module_enabled
from apps.integrations.fanout_jobs import deferred_fanout

SOURCE = "membership.broadcast"
SEGMENT_KEYS = {"plan_id", "status", "machine_type_id"}
LEGACY_SEGMENT_KEYS = SEGMENT_KEYS | {"certification_id"}


def load(envelope):
    return scoped(MemberBroadcast, envelope.makerspace_id).select_related(
        "makerspace", "created_by",
    ).filter(pk=envelope.source_id).first()


def broadcast_revision(row):
    # Private content is hashed, never copied into unencrypted context or audit.
    return revision(row.pk, row.created_at, row.title, row.body)


def _segment(space, segment):
    """Read old contexts without treating a certification as a live access grant."""
    if not isinstance(segment, dict) or set(segment) - LEGACY_SEGMENT_KEYS:
        return None
    segment = dict(segment)
    for key in ("plan_id", "machine_type_id", "certification_id"):
        if key in segment and (type(segment[key]) is not int or segment[key] < 1):
            return None
    if "status" in segment and segment["status"] not in ("active", "lapsed"):
        return None
    if "certification_id" in segment:
        if not module_enabled(space, "machines"):
            return None
        from apps.machines.models import CertificationType
        machine_type_id = scoped(CertificationType, space.pk).filter(
            Q(machine_type__makerspace_id=space.pk) | Q(machine_type__makerspace__isnull=True),
            pk=segment.pop("certification_id"),
        ).values_list("machine_type_id", flat=True).first()
        if machine_type_id is None or segment.get("machine_type_id", machine_type_id) != machine_type_id:
            return None
        segment["machine_type_id"] = machine_type_id
    return segment


def eligible(envelope):
    from apps.notifications.broadcasts import segment_members
    row = load(envelope)
    if (row is None or envelope.event != "broadcast" or envelope.audience == "staff"
            or not isinstance(envelope.context, dict)):
        return False
    space = row.makerspace
    segment = _segment(space, envelope.context.get("segment", {}))
    if segment is None:
        return False
    try:
        return bool(envelope.revision == broadcast_revision(row)
            and feature_enabled(space, "membership.broadcasts") and module_enabled(space, "membership")
            and module_enabled(space, "notifications") and row.created_by
            and rbac.can(row.created_by, rbac.Action.MANAGE_MEMBERS, space.pk)
            and segment_members(space, segment).filter(user_id=envelope.recipient_id).exists())
    except ValidationError:
        # Removed segments or disabled machines terminate through the delivery skip,
        # rather than leaving an unprocessed envelope to crash on every sweep.
        return False


def render(envelope):
    row = load(envelope)
    return body(row.title, row.body, local_link(row.makerspace, "member"))


# Broadcast creation and all recipient intents must succeed in the same transaction.
@deferred_fanout()
def notify_broadcast(row, *, user_id, segment):
    # Retained deferred jobs may still carry a legacy context; eligibility maps it
    # at delivery, or rejects it through the normal terminal skip contract.
    if not isinstance(segment, dict) or set(segment) - LEGACY_SEGMENT_KEYS:
        raise ValueError("Unknown member broadcast segment")
    user = User.objects.get(pk=user_id)
    return fanout(row=row, space=row.makerspace, feature="members", stream="membership", event="broadcast",
        source_kind=SOURCE, revision=broadcast_revision(row), owner=user,
        owner_body=body(row.title, row.body, local_link(row.makerspace, "member")),
        staff=False, context={"segment": segment})


def register():
    register_source(SOURCE, NotificationSource(eligible, render))
