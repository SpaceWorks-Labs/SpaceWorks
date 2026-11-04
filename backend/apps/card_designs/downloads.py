"""Download audit, throttled to one row per card per 10 minutes (SPEC §12)."""
from datetime import timedelta

from django.utils import timezone

from apps.audit import services as audit

WINDOW = timedelta(minutes=10)
ACTIONS = {"member_card": "member_card.downloaded", "programme_card": "id_programme.card_downloaded",
           "event_card": "event_card.downloaded"}


def record_download(actor, kind, card, fmt, side):
    from apps.audit.models import AuditLog
    action = ACTIONS[kind]
    since = timezone.now() - WINDOW
    if AuditLog.objects.filter(makerspace_id=card.makerspace_id, action=action, target_id=str(card.pk),
                               created_at__gte=since).exists():
        return None
    if kind == "member_card":
        return audit.record(actor, "member_card.downloaded", makerspace=card.makerspace, target=card,
                            meta={"card_id": card.pk, "format": fmt, "side": side})
    if kind == "programme_card":
        return audit.record(actor, "id_programme.card_downloaded", makerspace=card.makerspace, target=card,
                            meta={"card_id": card.pk, "format": fmt, "side": side})
    return audit.record(actor, "event_card.downloaded", makerspace=card.makerspace, target=card,
                        meta={"card_id": card.pk, "format": fmt, "side": side})
