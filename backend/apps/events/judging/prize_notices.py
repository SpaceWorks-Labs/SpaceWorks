"""Hack-money: the prize steps that told nobody now tell the winner.

`prize_split_proposed` (confirm your share), `prize_claim_verified` (your payee details were accepted),
`prize_forfeited` and `prize_recovery_opened`. One personal source, delivered through the existing outbox:
translated in the recipient's language, preferences and quiet hours respected, fanned out by Celery
(`deferred_fanout`). Rows are re-read at delivery only for "is the space still live"; the text is rendered
at emit time from ids captured at decision time, so a later correction cannot drop it.
"""

from django.utils.translation import gettext, gettext_noop
from apps.integrations.fanout_jobs import deferred_fanout
from apps.integrations.notification_links import local_link
from apps.integrations.notification_outbox import emit

PRIZE_STEP_SOURCE = "events.prize_step"
KINDS = {
    "prize_split_proposed": (gettext_noop("Confirm your share of the prize for %(title)s"),
                             gettext_noop("Your team leader proposed how the prize for %(title)s is shared. "
                                     "Open your prizes to confirm or decline your share.")),
    "prize_claim_verified": (gettext_noop("Your payee details for %(title)s were verified"),
                             gettext_noop("The organisers of %(title)s verified your payee details. "
                                     "Your prize can now be paid.")),
    "prize_forfeited": (gettext_noop("A prize for %(title)s was marked forfeited"),
                        gettext_noop("The claim window for your prize at %(title)s has closed, so the organisers "
                                "marked it forfeited. Contact them if you think this is a mistake.")),
    "prize_recovery_opened": (gettext_noop("A prize payment for %(title)s needs attention"),
                              gettext_noop("The result of %(title)s changed after your prize was paid, so the "
                                      "organisers opened a recovery for it. They will contact you.")),
}


@deferred_fanout()
def send_prize_step(event, recipient_id, kind, ref_id):
    from django.db import transaction
    from apps.accounts.models import User
    from apps.integrations.recipients_owners import eligible_owner
    if recipient_id is None or not eligible_owner(event.makerspace, recipient_id):
        return

    def send():
        user = User.objects.filter(pk=recipient_id).first()
        if user is None:
            return
        subject, text = KINDS[kind]
        emit(makerspace=event.makerspace, recipient=user, feature="events", stream="events", event=kind,
             audience="requester", dedup_key=f"ev:{PRIZE_STEP_SOURCE}:{kind}:{ref_id}:{recipient_id}",
             source_kind=PRIZE_STEP_SOURCE, source_id=str(ref_id), revision="1", subject=event,
             context={"event_id": event.pk, "ref_id": ref_id},
             rendered=lambda: {"subject": gettext(subject) % {"title": event.title},
                               "text": gettext(text) % {"title": event.title}, "html": "",
                               "link": local_link(event.makerspace, "member", "events/history")})
    transaction.on_commit(send)


def prize_step_notice(event, recipient_id, kind, ref_id):
    """Plain function so the call sites pass ids; the fan-out job carries only ids."""
    if kind not in KINDS:
        raise ValueError("Unknown prize notice.")
    send_prize_step(event, recipient_id, kind, ref_id)


def step_eligible(envelope):
    from apps.events.models import Event
    from apps.makerspaces.platform import feature_enabled, module_enabled
    from apps.makerspaces.servability import is_servable
    event = Event.objects.select_related("makerspace").filter(pk=envelope.context.get("event_id")).first()
    return bool(event and event.makerspace_id == envelope.makerspace_id and envelope.audience == "requester"
                and envelope.event in KINDS and is_servable(event.makerspace)
                and module_enabled(event.makerspace, "events") and feature_enabled(event.makerspace, "events.prize_payouts"))


def register():
    from apps.integrations.notification_sources import NotificationSource, register_source
    register_source(PRIZE_STEP_SOURCE, NotificationSource(step_eligible))
