"""Hack-money read gates shared by the prize views."""

from django.http import Http404


def finance_event(actor, event_id):
    """An event whose prize money this actor may read: RECORD_PAYMENT or the Event Manager (C-38)."""
    from apps.events.models import Event
    from .feature import PRIZE_PAYOUTS, require_capability
    from .payouts import may_record
    from .ports import runtime
    event = Event.objects.select_related("makerspace").filter(pk=event_id).first()
    if event is None or not may_record(actor, event.makerspace_id):
        raise Http404
    runtime().require_programme(event)
    require_capability(event, PRIZE_PAYOUTS)
    return event


def read_key(makerspace_id):
    """Best-effort decryption context for masked reads; a missing key only hides the masks."""
    from contextlib import nullcontext
    from .prize_claims import claim_key
    try:
        context = claim_key(makerspace_id, create=False)
        context.__enter__()
    except Exception:
        return nullcontext()
    return _Opened(context)


class _Opened:
    def __init__(self, context):
        self.context = context

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return self.context.__exit__(*exc)
