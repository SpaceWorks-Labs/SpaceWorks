"""Transactional domain fan-out shared by the equipment adapters.

Personal content goes only through explicit-recipient envelopes. Rooms retain the
existing transport, with a stable intent key and a separate staff-only body.
"""
import logging
from functools import wraps
from hashlib import sha256

from django.db import transaction

from apps.accounts.models import User
from apps.integrations.destinations import NotificationScope
from apps.integrations.notification_outbox import emit
from apps.integrations.notify import NotificationResult
from apps.integrations.staff_notifications import staff_user_ids_for_feature


logger = logging.getLogger(__name__)


def safe_adapter(function):
    """Fail safe INSIDE the domain transaction: a savepoint rolls back a failed
    query or insert before it is swallowed, so the workflow can still commit."""
    @wraps(function)
    def guarded(*args, **kwargs):
        try:
            with transaction.atomic():
                return function(*args, **kwargs)
        except Exception as exc:
            logger.warning("equipment_notification_failed",
                           extra={"adapter": function.__name__, "failure_type": type(exc).__name__})
            return None
    return guarded


def revision(*values):
    return sha256("|".join(str(value) for value in values).encode()).hexdigest()


def content(rendered, *, link=""):
    return {"subject": rendered["subject"], "text": rendered["text_body"],
            "html": rendered.get("html_body", ""), "link": link}


@transaction.atomic
def fanout(*, space, feature, stream, event, kind, source, version, subject,
           staff=None, owner=None, own=None, scope=None, context=None, rooms=True, room_body=None,
           intent_key=None):
    """One durable intent per source revision, audience and account.

    No channel is chosen here: preferences, mandatory email, suppression and live
    endpoint consent remain the responsibility of the Phase-1a resolver.
    """
    scope = scope or NotificationScope()
    context = context or {}
    base = intent_key or f"{kind}:{source}:{event}:{version}"
    envelopes = []
    from apps.accounts.principal_guards import is_anonymous_requester
    if owner is not None and own is not None and not owner.is_tenant_dump_stub and not is_anonymous_requester(owner):
        envelopes.append(emit(makerspace=space, recipient=owner, feature=feature,
            stream=stream, event=event, audience="requester",
            source_kind=kind, source_id=source, revision=version, subject=subject,
            scope=scope, context=context, rendered=own, timing_policy="immediate",
            dedup_key=f"{base}:requester:{owner.pk}"))
        # Compatibility path stays disabled when the shared owner-proof policy is installed.
        from .notifications_p2_contact import notify_owner
        notify_owner(envelopes[-1])
    if staff is not None:
        ids = staff_user_ids_for_feature(space, feature, event, scope)
        for user in User.objects.filter(pk__in=ids).order_by("pk"):
            envelopes.append(emit(makerspace=space, recipient=user, feature=feature,
                stream=stream, event=event, audience="staff",
                source_kind=kind, source_id=source, revision=version, subject=subject,
                scope=scope, context=context, rendered=staff, timing_policy="immediate",
                dedup_key=f"{base}:staff:{user.pk}"))
        if rooms:
            from .notifications_p2_rooms import queue_rooms
            queue_rooms(space=space, feature=feature, event=event, kind=kind,
                        source=source, version=version, subject=subject, scope=scope,
                        context=context, body=room_body if room_body is not None else staff.get("text", ""), key=base)
    # Scheduling is not proof of delivery. The outbox owns retry and recovery.
    return NotificationResult(bool(envelopes))
