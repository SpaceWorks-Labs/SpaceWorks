"""Matrix fan-out addressed by User identity, never free-text contact ownership."""

import logging
from dataclasses import dataclass, replace
from uuid import NAMESPACE_URL, uuid5

from django.db import transaction

from apps.accounts import rbac
from apps.makerspaces.platform import feature_enabled, module_enabled
from apps.notifications.models_inbox import NotificationInboxRow
from apps.notifications.inbox_scope import scope_snapshot
from apps.notifications.preferences import personal_enabled
from apps.integrations.recipients_addressed import addressed_recipients
from apps.integrations.recipients_owners import eligible_owner

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class InboxDelivery:
    user_id: int
    title: str
    summary: str
    link: str = ""


def safe_link(value):
    # Only local application paths; never a javascript URL, external origin or token URL.
    if not isinstance(value, str):
        return ""
    return value[:300] if (value.startswith("/") and not value.startswith("//")
                          and "\\" not in value and not any(ord(char) < 32 or ord(char) == 127 for char in value)) else ""


def write_envelope_inbox(envelope, rendered):
    """M's in-app adapter uses the same stable event identity as its push child."""
    from apps.notifications.inbox_scope import persisted_scope

    scope = persisted_scope(envelope.scope)
    audience = "member" if envelope.audience in {"member", "requester"} else "staff"
    with transaction.atomic():
        row, created = rbac.scope_notification_policy(
            NotificationInboxRow.objects.all(), makerspace_id=envelope.makerspace_id,
        ).get_or_create(makerspace_id=envelope.makerspace_id, user_id=envelope.recipient_id,
            event_key=uuid5(NAMESPACE_URL, envelope.dedup_key), defaults={
                "feature": envelope.feature, "event": envelope.event, "audience": audience,
                "scope": scope, "title": rendered.get("subject", "Space Works")[:200],
                "summary": rendered.get("text", "")[:2000], "link": safe_link(rendered.get("link", "")),
            })
        if created:
            transaction.on_commit(lambda: _hint(envelope.makerspace_id, envelope.recipient_id), robust=True)
            transaction.on_commit(lambda pk=row.pk: browser_alert(pk), robust=True)
    return row


def write_matrix_inbox(makerspace, feature, event, payload, event_key):
    from apps.tenant_migration.gate_runtime import tenant_write

    with tenant_write(makerspace.pk):
        makerspace.refresh_from_db()
        _write_matrix_inbox(makerspace, feature, event, payload, event_key)


def _write_matrix_inbox(makerspace, feature, event, payload, event_key):
    from apps.integrations.recipients import feature_available
    from apps.makerspaces.servability import is_servable

    if not is_servable(makerspace) or not module_enabled(makerspace, "notifications") or not feature_available(makerspace, feature):
        return
    member_enabled = feature_enabled(makerspace, "notifications.member_inbox")
    selection_payload = payload if member_enabled else replace(payload, emails=(), inbox=())
    selected = dict(addressed_recipients(makerspace, feature, event, selection_payload))
    recipients = {}
    member_ids = set()
    stored_scope = scope_snapshot(payload.scope)
    for user_id, audience in selected.items():
        if audience == "staff":
            recipients[user_id] = InboxDelivery(user_id,
                f"{feature.replace('_', ' ').title()}: {event.replace('_', ' ')}",
                payload.text, f"/m/{makerspace.slug}/admin/notifications")
    if member_enabled:
        own = [InboxDelivery(mail.user_id, mail.subject, mail.text_body,
                            f"/m/{makerspace.slug}/member") for mail in payload.emails
               if mail.user_id and mail.audience in {"requester", "member"}]
        own.extend(payload.inbox)
        for delivery in own:
            if selected.get(delivery.user_id) == "member":
                recipients[delivery.user_id] = delivery
                member_ids.add(delivery.user_id)
    for user_id, delivery in recipients.items():
        if not personal_enabled(makerspace, user_id, feature, "in_app", event=event):
            continue
        with transaction.atomic():
            row, created = rbac.scope_notification_policy(
                NotificationInboxRow.objects.all(), makerspace_id=makerspace.pk,
            ).get_or_create(
                makerspace=makerspace, user_id=user_id, event_key=event_key,
                defaults={"feature": feature, "event": event, "title": delivery.title[:200],
                          "audience": "member" if user_id in member_ids else "staff", "scope": stored_scope,
                          "summary": delivery.summary[:12000], "link": safe_link(delivery.link)},
            )
            if created:
                transaction.on_commit(lambda uid=user_id: _hint(makerspace.pk, uid), robust=True)
                transaction.on_commit(lambda pk=row.pk: browser_alert(pk), robust=True)


def _hint(makerspace_id, user_id):
    from apps.operations.live import _payload, publish, user_channel

    publish(user_channel(user_id), _payload("notification.created", makerspace_id, "", "", None))


def browser_alert(row_id):
    """Opt-in browser notification for a new inbox row (X38); dormant without VAPID keys."""
    from apps.notifications.browser_alerts import enqueue
    enqueue(row_id)
