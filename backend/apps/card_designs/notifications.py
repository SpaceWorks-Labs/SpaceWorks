"""Card notices (release 2 L3): card issued, design awaiting approval, "photo needs
update", job finished, programme decisions. All through the shared fan-out, so
preferences, consent and channels stay the resolver's job. Bodies never carry a
check-link token or any sensitive extra; links open authenticated pages.
"""
from django.utils.translation import gettext
import logging

from apps.integrations.notification_sources import NotificationSource, register_source
from apps.operations.notifications_p2 import body, fanout, revision, safe_notification, staff_link

logger = logging.getLogger(__name__)
CARD_SOURCE, DESIGN_SOURCE, PHOTO_SOURCE, JOB_SOURCE = (
    "card_designs.card_notice", "card_designs.design", "card_designs.photo_request", "card_designs.job")
FEATURE = {"member_card": "members", "programme_card": "members", "event_card": "members"}  # one "cards" preference


def _member_link(space):
    from apps.integrations.notification_links import local_link
    return local_link(space, "member", "cards")


@safe_notification
def _card(kind, card_id, event):
    from .holders import registered
    spec = registered().get(kind)
    card = spec.model().objects.filter(pk=card_id).first() if spec else None
    if card is None or not spec.account_id(card):
        return None
    from apps.accounts.models import User
    owner = User.objects.get(pk=spec.account_id(card))
    values = spec.snapshot(card)
    def copy():
        text = {"card_issued": lambda: gettext("Your card is ready. Open My cards to see, save or download it."),
                "event_card_issued": lambda: gettext("Your ID card for %(event)s is ready in My cards.")
                % {"event": values.get("event", gettext("the event"))},
                "programme_card_decided": lambda: gettext(
                    "There is news about your ID card request. Open My cards for details.")}[event]()
        return body(gettext("%(space)s: your card") % {"space": values.get("space", "Space Works")}, text,
                    _member_link(card.makerspace))
    return fanout(row=card, space=card.makerspace, feature=FEATURE[kind], stream="membership", event=event,
                  source_kind=CARD_SOURCE, revision=revision(kind, card.pk, event), owner=owner,
                  owner_body=copy,
                  staff=False, context={"card_id": card.pk, "holder_kind": kind})


def card_issued(kind, card_id):
    return _card(kind, card_id, "event_card_issued" if kind == "event_card" else "card_issued")


def programme_decided(card_id):
    return _card("programme_card", card_id, "programme_card_decided")


@safe_notification
def design_awaiting_approval(approval_id):
    from .models import CardDesignApproval
    row = CardDesignApproval.objects.select_related("design__makerspace").filter(pk=approval_id).first()
    if row is None:
        return None
    space = row.design.makerspace
    return fanout(row=row, space=space, feature="members", stream="membership", event="card_design_pending",
                  source_kind=DESIGN_SOURCE, revision=revision(row.pk, row.revision),
                  staff_body=lambda: body(
                      gettext("A card design is waiting for approval"),
                      gettext("A card design was submitted for approval. Open Member cards › Card design to review it."),
                      staff_link(space, "member-cards")))


def design_published(design_id):
    """Holders see the new design the next time they open or download a card; no notice.

    Publishing an event card design issues cards to the event's confirmed registrants (Q-I8).
    """
    from .models import CardDesign
    design = CardDesign.objects.filter(pk=design_id, domain="event_card", event__isnull=False).first()
    if design is None:
        return None
    try:
        from apps.events.id_cards import reconcile_event
        reconcile_event(design.event_id)
    except Exception:
        logger.warning("event_card_issue_after_publish_failed", extra={"design_id": design_id})
    return None


@safe_notification
def photo_requested(request_id, reminder=False):
    from .models import CardPhotoRequest
    from .holders import registered
    row = CardPhotoRequest.objects.filter(pk=request_id).first()
    if row is None or row.resolved_at:
        return None
    spec = registered().get(row.holder_kind)
    card = spec.model().objects.filter(pk=row.holder_id).first() if spec else None
    if card is None or not spec.account_id(card):
        return None
    from apps.accounts.models import User
    def copy():
        text = (gettext("Reminder: please add a new photo for your card.") if reminder else
                gettext("Please add a new photo for your card. Your card stays valid meanwhile."))
        if row.reason:
            text += " " + gettext("Note from the staff: %(note)s") % {"note": row.reason}
        return body(gettext("Your card needs a new photo"), text, _member_link(card.makerspace))
    return fanout(row=row, space=card.makerspace, feature=FEATURE[row.holder_kind], stream="membership",
                  event="card_photo_requested", source_kind=PHOTO_SOURCE,
                  revision=revision(row.pk, "reminder" if reminder else "request"),
                  owner=User.objects.get(pk=spec.account_id(card)),
                  owner_body=copy, staff=False)


@safe_notification
def job_finished(job_id):
    from .models import CardJob
    job = CardJob.objects.select_related("makerspace", "requested_by").filter(pk=job_id).first()
    if job is None or job.requested_by is None or job.kind not in ("bulk_sheet", "bulk_per_person", "zip", "email"):
        return None
    def copy():
        text = {"succeeded": lambda: gettext("Your card job has finished. The file is ready for 7 days."),
                "failed": lambda: gettext("Your card job could not finish. Try again or narrow the selection."),
                "cancelled": lambda: gettext("Your card job was cancelled.")}.get(
            job.state, lambda: gettext("Your card job changed."))()
        return body(gettext("Card job %(state)s") % {"state": job.get_state_display().lower()}, text,
                    staff_link(job.makerspace, "member-cards"))
    return fanout(row=job, space=job.makerspace, feature="members", stream="membership", event="card_job_finished",
                  source_kind=JOB_SOURCE, revision=revision(job.pk, job.state), owner=job.requested_by,
                  owner_body=copy, staff=False)


def _eligible_card(envelope):
    from .holders import registered
    kind = (envelope.context or {}).get("holder_kind")
    spec = registered().get(kind)
    card = spec.model().objects.filter(pk=envelope.source_id, makerspace_id=envelope.makerspace_id).first() if spec else None
    return bool(card and spec.account_id(card) == envelope.recipient_id and spec.standing(card) is not None)


def _eligible_design(envelope):
    from .models import CardDesignApproval
    return CardDesignApproval.objects.filter(pk=envelope.source_id, decision="pending",
                                             design__makerspace_id=envelope.makerspace_id).exists()


def _eligible_photo(envelope):
    from .models import CardPhotoRequest
    return CardPhotoRequest.objects.filter(pk=envelope.source_id, makerspace_id=envelope.makerspace_id,
                                           resolved_at__isnull=True).exists()


def _eligible_job(envelope):
    from .models import CardJob
    return CardJob.objects.filter(pk=envelope.source_id, makerspace_id=envelope.makerspace_id,
                                  requested_by_id=envelope.recipient_id).exists()


def register():
    register_source(CARD_SOURCE, NotificationSource(_eligible_card))
    register_source(DESIGN_SOURCE, NotificationSource(_eligible_design))
    register_source(PHOTO_SOURCE, NotificationSource(_eligible_photo))
    register_source(JOB_SOURCE, NotificationSource(_eligible_job))
