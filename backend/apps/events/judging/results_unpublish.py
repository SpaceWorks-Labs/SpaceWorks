"""Parity E-B4 (D8): withdraw published results and re-announce them without a second email.

Unpublishing only clears the public pointer. The immutable result revision and its announcement stay,
and a notice that was not delivered yet cancels itself because delivery re-checks that the result is
still the published one (`provider_notices.recipients`). Publishing again re-points the same
announcement and emails only people whose earlier message was cancelled, never anyone who already got it.
"""

from django.utils.translation import gettext
import logging

from django.db import transaction
from django.db.models import Q

from apps.accounts.models import User
from apps.accounts.staff_identity import person_q
from apps.integrations.models_contract import NotificationEnvelope
from apps.integrations.notification_outbox import emit
from .boundary import audit, command, mutation, notice
from .errors import ProgrammeError
from .models_payouts import HackathonPrizePayout
from .models_prize_money import HackathonPrizeShare
from .models_results import JudgingNotice, ResultPublicationState
from .provider_notices import SOURCE, recipients
from .serializers import CommandInput, validated
from apps.integrations.fanout_jobs import deferred_fanout

logger = logging.getLogger(__name__)
LIVE = {"accepted", "sent", "delivered", "read", "retrying", "held"}


def unpublish(event_id, *, actor, data):
    values = validated(CommandInput, data)
    with mutation(event_id, actor, permission=None) as (event, _):
        def run():
            state = ResultPublicationState.objects.select_for_update(of=("self",)).select_related(
                "current_announcement__result").filter(event=event).first()
            if state is None or state.current_announcement_id is None:
                raise ProgrammeError("not_published", gettext("These results are not published."))
            result = state.current_announcement.result
            if values["expected_version"] != result.version:
                raise ProgrammeError("stale_version", gettext("This item changed."), current_version=result.version)
            award_ids = list(result.awards.values_list("pk", flat=True))
            if (HackathonPrizePayout.objects.filter(event=event, award_id__in=award_ids).exists()
                    or HackathonPrizeShare.objects.filter(event=event, award_id__in=award_ids).exists()):
                raise ProgrammeError("results_in_use", gettext("Prizes were already claimed or paid for these results."))
            state.current_announcement = None
            state.version += 1
            state.save()
            audit(event, actor, "results_unpublished", state, version=result.version, result_id=result.pk)
            return {"id": result.pk, "event_id": event_id, "version": result.version,
                    "state": "finalized", "allowed_actions": ["publish", "correct"]}
        return command(event, actor, values, path="results/unpublish", run=run)


@deferred_fanout()
def republish_emails(event, result, epoch):
    """Called inside `publish` when withdrawn results are published again; `epoch` is the pointer version."""
    from .options import option
    row = JudgingNotice.objects.filter(event=event, kind="results_published", source_id=result.pk,
                                       revision=result.version).first()
    if row is None:
        if option(event, "results_email"):
            notice(event, "results_published", result.pk, result.version)
        return

    def send():
        try:
            deliver_cancelled(row.pk, epoch)
        except Exception:
            logger.warning("event_results_republish_email_failed", extra={"notice_id": row.pk})
    transaction.on_commit(send)


def _in_flight_or_sent(envelope):
    states = set(envelope.deliveries.values_list("state", flat=True))
    return bool(states & LIVE) or not (envelope.processed_at is not None or states)


def deliver_cancelled(notice_id, epoch):
    """Emit to recipients with no live or sent message; a cancelled one gets a fresh dedup key per epoch."""
    row = JudgingNotice.objects.select_related("event__makerspace").get(pk=notice_id)
    for user in User.objects.filter(person_q(), pk__in=recipients(row), is_active=True, access_status="active",
                                    is_tenant_dump_stub=False).order_by("pk"):
        key = f"event-judging:{row.pk}:{row.revision}:{user.pk}"
        earlier = list(NotificationEnvelope.objects.filter(Q(dedup_key=key) | Q(dedup_key__startswith=f"{key}:p")))
        if any(_in_flight_or_sent(envelope) for envelope in earlier):
            continue  # Delivered, in flight or still queued: never a second copy.
        if earlier:
            key = f"{key}:p{epoch}"  # Every earlier message was cancelled: a fresh key per publication.
        emit(makerspace=row.event.makerspace, recipient=user, feature="events", stream="events",
             event=row.kind, audience="member", dedup_key=key, source_kind=SOURCE, source_id=str(row.pk),
             revision=str(row.revision), subject=row.event, context={"event_id": row.event_id}, rendered={})
