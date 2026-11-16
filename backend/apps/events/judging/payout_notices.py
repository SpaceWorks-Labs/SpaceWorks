"""Personal notices added by lane L21b: a recorded prize payout tells its winner.

The finalists email rides the existing judging notice source (``finalists_announced``, behind the
per-event switch); charges for entry fees and team registration use the payments notices that
``create_payment`` already sends. The live check re-reads the payout row: it must still stand
(not reversed), belong to the recipient and sit in a servable space with events on.
"""

from django.utils.translation import gettext
from apps.integrations.notification_links import local_link
from apps.integrations.notification_outbox import emit
from apps.integrations.fanout_jobs import deferred_fanout

PAYOUT_SOURCE = "events.prize_payout"


@deferred_fanout()
def payout_recorded_notice(payout):
    from django.db import transaction
    from apps.accounts.models import User
    from apps.integrations.recipients_owners import eligible_owner
    event = payout.event
    if payout.recipient_id is None or not eligible_owner(event.makerspace, payout.recipient_id):
        return

    def send():
        emit(makerspace=event.makerspace, recipient=User.objects.get(pk=payout.recipient_id), feature="events",
             stream="events", event="prize_payout_recorded", audience="requester",
             dedup_key=f"ev:{PAYOUT_SOURCE}:{payout.pk}:prize_payout_recorded:1", source_kind=PAYOUT_SOURCE,
             source_id=str(payout.pk), revision="1", subject=payout, context={"event_id": event.pk, "payout_id": payout.pk},
             rendered=lambda: {
                 "subject": gettext("Your prize for %(title)s was paid") % {"title": event.title},
                 "text": gettext("The organisers of %(title)s recorded your prize payment: %(amount)s "
                                 "(%(prize)s).") % {"title": event.title, "amount": _paid_text(payout),
                                                    "prize": payout.prize.name},
                 "html": "", "link": local_link(event.makerspace, "member", "events/history")})
    transaction.on_commit(send)


def _paid_text(payout):
    """What reached the winner (net of any tax deducted), always with its currency: "INR 4500.00"."""
    from apps.payments.money import money_text
    net = payout.net_amount if payout.net_amount is not None else payout.amount - payout.tds_amount
    return f"{payout.currency.upper()} {money_text(net)}"


def payout_eligible(envelope):
    from apps.makerspaces.platform import module_enabled
    from apps.makerspaces.servability import is_servable
    from .models_payouts import HackathonPrizePayout
    row = HackathonPrizePayout.objects.select_related("event__makerspace").filter(
        pk=envelope.context.get("payout_id"), kind="payout").first()
    return bool(row and str(row.pk) == str(envelope.source_id) and row.recipient_id == envelope.recipient_id
                and not HackathonPrizePayout.objects.filter(reverses=row).exists()
                and row.event.makerspace_id == envelope.makerspace_id and envelope.audience == "requester"
                and is_servable(row.event.makerspace) and module_enabled(row.event.makerspace, "events"))


def register():
    from apps.integrations.notification_sources import NotificationSource, register_source
    register_source(PAYOUT_SOURCE, NotificationSource(payout_eligible))
