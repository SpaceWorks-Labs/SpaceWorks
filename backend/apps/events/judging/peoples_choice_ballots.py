"""Staff view of People's choice ballots and the void action (#181 S3).

Staff see who voted (to spot throwaway or duplicate accounts), never which project each person
chose; rows are ordered by the opaque handle, not by time. A void needs a reason, keeps the row
(so the voter cannot vote again) and is final once the result is published.
"""

from django.utils.translation import gettext
from django.http import Http404
from django.utils import timezone

from apps.audit.services import record
from .boundary import command, mutation
from .errors import ProgrammeError, require_version
from .feature import PEOPLES_CHOICE, require_capability
from .models_peoples_choice import PeoplesChoiceVote
from .models_scoring import JudgingReason
from .peoples_choice import result_for, staff_event
from .serializers import validated
from .serializers_peoples_choice import PeoplesChoiceVoidInput, PeoplesChoiceVoteRowRead


def _attendees(event):
    from apps.events.models import EventRegistration
    return set(EventRegistration.objects.filter(event=event, status=EventRegistration.Status.ATTENDED,
                                                member__isnull=False).values_list("member_id", flat=True))


def row_projection(vote, *, published, attendees):
    voter = vote.voter
    name = (voter.display_name or voter.username) if voter else "Deleted account"
    return {"handle": vote.handle, "voter_name": name, "attended": vote.voter_id in attendees,
            "changed": vote.changed_at is not None, "voided": vote.voided_at is not None,
            "void_reason": vote.void_reason.body if vote.void_reason_id else None, "version": vote.version,
            "allowed_actions": [] if published or vote.voided_at else ["void"]}


def listing(event_id, *, actor):
    event = staff_event(actor, event_id)
    published, attendees = result_for(event) is not None, _attendees(event)
    rows = PeoplesChoiceVote.objects.filter(event=event).select_related("voter", "void_reason").order_by("handle")
    return event, [row_projection(row, published=published, attendees=attendees) for row in rows]


def void(event_id, handle, *, actor, data):
    values = validated(PeoplesChoiceVoidInput, data)
    with mutation(event_id, actor, gallery=True) as (event, _):
        require_capability(event, PEOPLES_CHOICE)

        def run():
            if result_for(event) is not None:
                raise ProgrammeError("already_published", gettext("The People's choice result is published; ballots are final."))
            vote = PeoplesChoiceVote.objects.select_for_update().filter(event=event, handle=handle).first()
            if vote is None:
                raise Http404
            require_version(vote, values["expected_version"])
            if vote.voided_at is not None:
                raise ProgrammeError("already_voided", gettext("This vote is already voided."))
            vote.void_reason = JudgingReason.objects.create(event=event, makerspace_id=event.makerspace_id,
                                                            actor=actor, body=values["reason"])
            vote.voided_at, vote.voided_by, vote.version = timezone.now(), actor, vote.version + 1
            vote.save(update_fields=["void_reason", "voided_at", "voided_by", "version"])
            record(actor, "event.peoples_choice.vote_voided", makerspace=event.makerspace, target=vote,
                   meta={"event_id": event.pk, "vote_id": vote.pk})
            # JSON-safe for the command receipt; the view masks the name for a superadmin.
            return PeoplesChoiceVoteRowRead(row_projection(vote, published=False, attendees=_attendees(event))).data
        return command(event, actor, values, path=f"peoples-choice/votes/{handle}/void", run=run)
