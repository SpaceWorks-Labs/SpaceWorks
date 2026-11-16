"""Set-based, bounded audit provenance for venue payments; fail closed on ambiguity."""
from collections import defaultdict

from django.db.models.fields.json import KeyTextTransform

from apps.audit.models import AuditLog
from apps.payments.models import Payment

MAX_SAFE = 9007199254740991
# Bound Python materialization and SQL IN size. Exceeding either needs finance handoff.
MAX_PAYMENTS = 1000
MAX_AUDITS = 4000


def history_state(maker_id, event_id):
    """Classify history without assuming an orphan subject ID cannot collide on import."""
    payments = list(Payment.objects.filter(makerspace_id=maker_id, subject_type="event_venue_fee")
                    .order_by("pk").values_list("pk", "subject_id")[:MAX_PAYMENTS + 1])
    if len(payments) > MAX_PAYMENTS:
        return "unresolved"
    if not payments:
        return "none"
    subjects = dict(payments)
    audits = list(AuditLog.objects.filter(
        makerspace_id=maker_id, action="event.venue_fee_charged", target_type="events.eventvenuefee",
    ).annotate(payment_key=KeyTextTransform("payment_id", "meta"))
        .filter(payment_key__in=[str(pk) for pk in subjects]).order_by()
        .values_list("target_id", "meta")[:MAX_AUDITS + 1])
    if len(audits) > MAX_AUDITS:
        return "unresolved"
    events = defaultdict(set)
    for target_id, meta in audits:
        if not isinstance(meta, dict):
            return "unresolved"
        payment_id, old_event = meta.get("payment_id"), meta.get("event_id")
        if type(payment_id) is not int or payment_id not in subjects:
            return "unresolved"
        if type(old_event) is not int or not 0 < old_event <= MAX_SAFE:
            return "unresolved"
        if str(subjects[payment_id]) != target_id:
            return "unresolved"
        events[payment_id].add(old_event)
    if any(len(events[pk]) != 1 for pk in subjects):
        return "unresolved"
    return "historical_debt" if any(event_id in ids for ids in events.values()) else "none"
