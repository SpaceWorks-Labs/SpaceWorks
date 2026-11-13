"""People's choice ballots (#181 S3): one per person per event, cast on a live public gallery project.

Only final-stage gallery work can be chosen (`stage_gallery.final_stage_entries`, #178/#180 S18): an
earlier stage made public early is shown in the gallery but never stands for the award.

Abuse protection, in layers: the vote route has its own per-account throttle; the database holds
one ballot per (event, voter); a voter may never choose a project of a team they are on; a staff
void keeps the row, so a voided voter cannot simply vote again. A ballot may be changed until
voting closes. Audit rows name the event only, never the project chosen.
"""

from django.utils.translation import gettext
from django.http import Http404
from django.utils import timezone

from apps.audit.services import record
from apps.events.submissions.gallery_models import GalleryEntry
from apps.events.submissions.gallery_projection import live_entry
from apps.events.submissions.stage_gallery import final_stage_entries
from .boundary import command, mutation
from .errors import ProgrammeError
from .feature import PEOPLES_CHOICE, require_capability
from .models_peoples_choice import PeoplesChoiceVote
from .peoples_choice import attended, config_for, public_gallery_event, require_live, result_for, state, window
from .serializers import validated
from .serializers_peoples_choice import PeoplesChoiceBallotRead, PeoplesChoiceVoteInput

MESSAGES = {
    "off": "People's choice voting is not running for this event.",
    "not_open": "People's choice voting has not opened yet.",
    "closed": "People's choice voting has closed.",
    "published": "The People's choice result is published; voting has ended.",
    "attendees_only": "Only checked-in attendees can vote in this People's choice.",
    "voided": "Your People's choice vote was voided by the organisers.",
}
_STATE_REFUSAL = {"off": "off", "scheduled": "not_open", "closed": "closed", "published": "published"}


def refusal(event, config, result, voter, vote=None):
    """Why this person may not vote now, or None."""
    current = state(config, result)
    if current != "open":
        return _STATE_REFUSAL[current]
    if vote is not None and vote.voided_at is not None:
        return "voided"
    if config.audience == "attendees" and not attended(event, voter.pk):
        return "attendees_only"
    return None


def own_team_ids(event, member_id):
    from apps.events.models import HackathonTeam
    return set(HackathonTeam.objects.filter(event=event, memberships__member_id=member_id,
                                            memberships__state="active").values_list("pk", flat=True))


def _entry_for_team(event, team_id):
    rows = GalleryEntry.objects.filter(event=event, snapshot__submission__team_id=team_id, hidden_at__isnull=True)
    return final_stage_entries(event.pk, rows).order_by("-pk").values_list("public_id", flat=True).first()


def ballot_projection(event, voter):
    config, result = config_for(event), result_for(event)
    vote = PeoplesChoiceVote.objects.filter(event=event, voter=voter).first()
    reason = refusal(event, config, result, voter, vote)
    own = [entry for team in own_team_ids(event, voter.pk) if (entry := _entry_for_team(event, team))]
    return {"event_id": event.pk, "state": state(config, result), **window(config), "can_vote": reason is None,
            "refusal": reason, "entry_public_id": _entry_for_team(event, vote.team_id) if vote and not vote.voided_at else None,
            "own_entry_public_ids": own, "version": vote.version if vote else 0}


def ballot(event, *, actor):
    require_live(event)
    public_gallery_event(event)
    return ballot_projection(event, actor)


def cast(event_id, *, actor, data):
    values = validated(PeoplesChoiceVoteInput, data)
    with mutation(event_id, actor, owner=True, gallery=True) as (event, _):
        require_capability(event, PEOPLES_CHOICE)
        public_gallery_event(event)

        def run():
            config, result = config_for(event), result_for(event)
            vote = PeoplesChoiceVote.objects.select_for_update().filter(event=event, voter=actor).first()
            if (vote.version if vote else 0) != values["expected_version"]:
                raise ProgrammeError("stale_version", gettext("Your vote changed."), current_version=vote.version if vote else 0)
            reason = refusal(event, config, result, actor, vote)
            if reason:
                raise ProgrammeError(reason, MESSAGES[reason], status=403)
            entry = final_stage_entries(event.pk, GalleryEntry.objects.select_related("event", "publication").filter(
                event=event, public_id=values["entry_public_id"])).first()  # Never an early-stage entry.
            if entry is None:
                raise Http404
            snapshot, _consent = live_entry(entry)  # Only a live, consented, eligible public project.
            if actor.pk in snapshot.member_ids or snapshot.team_id in own_team_ids(event, actor.pk):
                raise ProgrammeError("own_project", gettext("You cannot vote for your own team's project."), status=403)
            if vote is not None and vote.team_id == snapshot.team_id:
                return PeoplesChoiceBallotRead(ballot_projection(event, actor)).data  # The same choice again changes nothing.
            changed = vote is not None
            if vote is None:
                PeoplesChoiceVote.objects.create(event=event, voter=actor, team_id=snapshot.team_id)
            else:
                vote.team_id, vote.version, vote.changed_at = snapshot.team_id, vote.version + 1, timezone.now()
                vote.save(update_fields=["team", "version", "changed_at"])
            # Never the project or the team: the audit trail must not become a ballot record.
            record(actor, "event.peoples_choice.ballot_cast", makerspace=event.makerspace, target=event,
                   meta={"event_id": event.pk, "changed": changed})
            return PeoplesChoiceBallotRead(ballot_projection(event, actor)).data
        return command(event, actor, values, path="peoples-choice/vote", run=run)
