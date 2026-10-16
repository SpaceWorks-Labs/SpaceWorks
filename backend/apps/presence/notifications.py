"""Presence expiry uses personal inbox/push envelopes, never a staff room."""
from datetime import timedelta

from django.utils import timezone

from apps.integrations.notification_outbox import emit
from apps.integrations.notification_sources import NotificationSource, register_source
from .models import PresenceSession
from .policy import require_enabled

KIND = "presence.expiry"


def eligible(envelope):
    try:
        require_enabled(envelope.makerspace)
    except Exception:
        return False
    row = PresenceSession.objects.filter(pk=envelope.source_id, makerspace_id=envelope.makerspace_id,
        account_id=envelope.recipient_id, revision=envelope.revision,
        end_reason="expired", expires_at__gte=timezone.now() - timedelta(minutes=10)).first()
    return bool(row and not PresenceSession.objects.filter(account_id=row.account_id,
        makerspace_id=row.makerspace_id, started_at__gt=row.started_at).exists())


def remind(row):
    from apps.notifications.models_preferences import NotificationPreference
    # Presence's product default is push + web. Existing explicit selections win.
    NotificationPreference.objects.get_or_create(makerspace=row.makerspace, user=row.account,
        category="presence", defaults={"channels": ["in_app", "native_push"], "email_fallback": False})
    return emit(makerspace=row.makerspace, recipient=row.account, feature="presence", stream="presence",
        event="expired", audience="member", source_kind=KIND, source_id=row.pk,
        revision=str(row.revision), dedup_key=f"presence:expired:{row.pk}:{row.revision}", subject=row,
        rendered={"subject": "Your presence check-in has expired",
                  "text": "Still here? Renew your presence check-in to stay on the display."})


def register():
    register_source(KIND, NotificationSource(eligible))
