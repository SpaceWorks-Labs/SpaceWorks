"""Shared transactional fan-out for the Phase-2 domain adapters.

Personal bodies belong to envelopes; only a separate, bounded staff summary is
ever handed to the existing room dispatcher. No transport runs in this module.
"""
import hashlib
import logging
from functools import wraps

from django.db import transaction

from apps.accounts import rbac
from apps.accounts.models import User
from apps.integrations.notification_outbox import emit
from apps.integrations.notify import NotificationResult
from apps.integrations.staff_notifications import staff_user_ids_for_feature

logger = logging.getLogger(__name__)
ROOM_CHANNELS = ("telegram", "slack", "mattermost", "discord", "webhook")


def safe_notification(function):
    @wraps(function)
    def guarded(*args, **kwargs):
        try:
            # A failed INSERT must roll back its savepoint before being swallowed,
            # otherwise Django would leave the domain transaction unusable.
            with transaction.atomic():
                return function(*args, **kwargs)
        except Exception as exc:
            logger.warning("domain_notification_failed", extra={
                "adapter": function.__name__, "failure_type": type(exc).__name__,
            })
            return NotificationResult(False, failed_counts={"outbox": 1})
    return guarded


def scoped(model, space_id, *, field="makerspace_id"):
    return rbac.scope_notification_policy(model.objects.all(), makerspace_id=space_id, field=field)


def identity(*parts):
    return hashlib.sha256("\x1f".join(str(part) for part in parts).encode()).hexdigest()


def revision(*parts):
    return identity(*parts)


def body(subject, text, link="", html=""):
    return {"subject": subject, "text": text, "html": html, "link": link}


def staff_link(space, tab):
    # Bind navigation to the source tenant, rather than a browser's last-picked
    # makerspace. These are ordinary authenticated console routes, never grants.
    return f"/m/{space.slug}/admin/{tab}"


def template(space, stream, audience, event, context, *, link=""):
    from apps.integrations.email_templates import render
    value = render(space, stream, audience, event, context)
    return body(value["subject"], value["text_body"], link, value["html_body"])


def finish_reminder(space, reminder, now, result):
    """Commit a permanent reminder completion together with its outbox intents.

    The sweeper's subsequent completion is deliberately idempotent. Transport
    delivery/retries now belong to the envelope, not to the permanent claim.
    """
    from .reminder_services import complete_reminder
    complete_reminder(makerspace=space, reminder_id=reminder.pk,
        claim_token=reminder.claim_token, now=now, failed=bool(result and result.failed_counts))


def fanout(*, row, space, feature, stream, event, source_kind, revision,
           owner=None, owner_body=None, staff_body=None, context=None, scope=None,
           staff=True, rooms=True, staff_context=None):
    """Call inside the domain transaction; repeat calls reserve the same intent."""
    from apps.integrations import recipients
    from apps.integrations.destinations import NotificationScope
    from apps.integrations.notification_catalog import is_notification_enabled
    from apps.integrations.dispatch_channels import dispatch_channel
    from apps.integrations.models import NotificationDeliveryLog
    from apps.makerspaces.servability import is_servable

    if not is_servable(space):
        return NotificationResult(False)
    context = context or {}
    scope = scope or NotificationScope()
    key = identity(space.pk, source_kind, row.pk, revision, event)
    envelopes = []
    # The domain owner is explicit, and may have no membership at all.
    if owner is not None and owner_body is not None and (
        not recipients.has_selection(space, feature, event, scope)
        or recipients.requester_selected(space, feature, event, scope)
    ):
        envelopes.append(emit(makerspace=space, recipient=owner, feature=feature,
            stream=stream, event=event, audience="requester", source_kind=source_kind,
            source_id=row.pk, subject=row, revision=revision, scope=scope,
            dedup_key=f"p2:{key}:u:{owner.pk}", context=context, rendered=owner_body))
    staff_ids = staff_user_ids_for_feature(space, feature, event, scope) if staff else []
    for account in User.objects.filter(pk__in=staff_ids).order_by("pk"):
        if owner is not None and owner.pk == account.pk and envelopes:
            continue
        envelopes.append(emit(makerspace=space, recipient=account, feature=feature,
            stream=stream, event=event, audience="staff", source_kind=source_kind,
            source_id=row.pk, subject=row, revision=revision, scope=scope,
            dedup_key=f"p2:{key}:u:{account.pk}", context=context,
            rendered=staff_body or body("Space Works", "A staff update is available.")))
    if staff and rooms and staff_body and space.staff_notifications_enabled:
        from apps.integrations.chat_templates import render_chat_text
        room_text = render_chat_text(space, feature, event, staff_body["text"], staff_context)
        for channel in ROOM_CHANNELS:
            if not is_notification_enabled(space, feature, channel):
                continue
            # Domain row locks serialize repeated edge emission. The room logs
            # themselves commit with the edge, including a recoverable body.
            if scoped(NotificationDeliveryLog, space.pk).filter(
                channel=channel, payload__p2_intent=key,
            ).exists():
                continue
            dispatch_channel(makerspace=space, channel=channel, feature=feature,
                event=event, text_body=room_text, scope=scope,
                payload={"p2_intent": key, "source_kind": source_kind,
                         "source_id": str(row.pk), "revision": revision})
    return NotificationResult(bool(envelopes))


def direct_mail_unless_routed(*, space, source_kind, row, revision, event, owner, to_email,
                              subject, text, stream, audience, feature, sync=False, persist_body=True,
                              address_owner=True):
    """Keep a pre-Phase-2 direct email (welcome, verification, invitation, payment
    document) that the members/payments matrix never governed and whose email cell
    defaults OFF. It is sent after commit unless the owner's own envelope will
    already email the same message, so there is never a second copy."""
    from apps.integrations.dispatch import dispatch_email
    from apps.integrations.models import EmailLog
    from apps.integrations.models_contract import NotificationEnvelope
    from apps.integrations.notification_resolution import resolve
    if not to_email:
        return None
    key = f"p2:{identity(space.pk, source_kind, row.pk, revision, event)}:u:{owner.pk if owner else '-'}"
    envelope = NotificationEnvelope.objects.filter(dedup_key=key).first() if owner else None
    if envelope is not None and any(target.channel == "email" for target in resolve(envelope)):
        return None

    def send():
        if scoped(EmailLog, space.pk).filter(source_metadata__p2_direct=key).exists():
            return
        dispatch_email(makerspace=space, to_email=to_email, subject=subject, text_body=text,
            stream=stream, event=event, audience=audience, feature=feature, sync=sync,
            persist_body=persist_body, recipient_id=owner.pk if owner and address_owner else None,
            source_metadata={"p2_direct": key})

    transaction.on_commit(send, robust=True)
    return key
