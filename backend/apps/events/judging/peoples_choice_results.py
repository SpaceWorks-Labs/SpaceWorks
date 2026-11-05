"""People's choice count and its one publication (#181 S3).

Only a live public gallery project counts: a project hidden, withdrawn, disqualified or no longer
current at publication loses its votes. Ranking is standard competition ranking (1, 1, 3); every
project tied at the top wins jointly, and a count with no votes has no winner. Before publication
the count is staff-only (manage_hackathon); the public, voters and teams see no number at all.
"""

from django.db.models import Count
from django.http import Http404
from django.utils import timezone

from apps.audit.services import record
from apps.events.submissions.gallery_models import GalleryConsent, GalleryEntry
from apps.events.submissions.gallery_projection import live_entry
from .boundary import command, mutation
from .errors import ProgrammeError, invalid, require_version
from .feature import PEOPLES_CHOICE, enabled, require_capability
from .models_peoples_choice import PeoplesChoiceConfig, PeoplesChoiceStanding, PeoplesChoiceResult, PeoplesChoiceVote
from .peoples_choice import DEFAULT_NAME, config_for, result_for, staff_event, state, window
from .ports import runtime
from .serializers import CommandInput, validated
from .serializers_peoples_choice import StandingsRead


def _live_entries(event):
    """team_id -> (entry, snapshot) for every live public gallery project."""
    found = {}
    for entry in GalleryEntry.objects.filter(event=event, hidden_at__isnull=True).select_related(
            "event", "publication").order_by("pk"):
        try:
            snapshot, _consent = live_entry(entry)
        except Http404:
            continue
        found.setdefault(snapshot.team_id, (entry, snapshot))
    return found


def tally(event):
    entries = _live_entries(event)
    counts = dict(PeoplesChoiceVote.objects.filter(event=event, voided_at__isnull=True, team_id__in=list(entries))
                  .values("team_id").annotate(n=Count("pk")).values_list("team_id", "n"))
    rows = [{"id": None, "snapshot_id": snapshot.id, "title": snapshot.title, "votes": counts[team]}
            for team, (_entry, snapshot) in entries.items() if counts.get(team)]
    rows.sort(key=lambda row: (-row["votes"], row["title"].lower(), row["snapshot_id"]))
    for row in rows:
        row["rank"] = 1 + sum(1 for other in rows if other["votes"] > row["votes"])
        row["winner"] = row["rank"] == 1
    return rows


def standings_projection(event):
    result = result_for(event)
    if result is None:
        config = config_for(event)
        rows = tally(event)
        return {"published": False, "published_at": None, "total_votes": sum(row["votes"] for row in rows),
                "prize_name": config.prize.name if config and config.prize_id else DEFAULT_NAME, "standings": rows}
    rows = [{"id": row.pk, "snapshot_id": row.submission_snapshot_id, "votes": row.votes, "rank": row.rank,
             "winner": row.winner, "title": runtime().snapshot(row.submission_snapshot_id).title}
            for row in result.standings.order_by("rank", "pk")]
    return {"published": True, "published_at": result.published_at, "total_votes": result.total_votes,
            "prize_name": result.prize_name, "standings": rows}


def standings(event_id, *, actor):
    return standings_projection(staff_event(actor, event_id))


def publish(event_id, *, actor, data):
    values = validated(CommandInput, data)
    with mutation(event_id, actor, gallery=True) as (event, _):
        require_capability(event, PEOPLES_CHOICE)

        def run():
            # No select_related here: the prize FK is nullable, and Postgres refuses FOR UPDATE across it.
            config = PeoplesChoiceConfig.objects.select_for_update().filter(event=event).first()
            if config is None:
                invalid("Switch People's choice on for this event first.")
            require_version(config, values["expected_version"])
            if result_for(event) is not None:
                raise ProgrammeError("already_published", "The People's choice result is already published.")
            if state(config, None) != "closed":
                invalid("Close voting before publishing: set the closing time to now or earlier.")
            rows = tally(event)
            result = PeoplesChoiceResult.objects.create(
                event=event, prize=config.prize, prize_name=config.prize.name if config.prize_id else DEFAULT_NAME,
                total_votes=sum(row["votes"] for row in rows), published_at=timezone.now(), published_by=actor)
            for row in rows:
                PeoplesChoiceStanding.objects.create(result=result, submission_snapshot_id=row["snapshot_id"],
                                                     votes=row["votes"], rank=row["rank"], winner=row["winner"])
            record(actor, "event.peoples_choice.published", makerspace=event.makerspace, target=result,
                   meta={"event_id": event.pk, "prize_id": config.prize_id, "total_votes": result.total_votes,
                         "winners": sum(1 for row in rows if row["winner"])})
            return StandingsRead(standings_projection(event)).data
        return command(event, actor, values, path="peoples-choice/publish", run=run)


def _public_winners(event, result):
    winners = []
    for row in result.standings.filter(winner=True).order_by("pk"):
        snapshot = runtime().snapshot(row.submission_snapshot_id)
        consented = GalleryConsent.objects.filter(event=event, snapshot_id=snapshot.id, metadata_public=True).exists()
        if not (snapshot.current and snapshot.eligible and snapshot.event_id == event.pk and consented):
            continue  # A winner that later left the gallery is not named publicly.
        entry = GalleryEntry.objects.filter(event=event, snapshot_id=snapshot.id, hidden_at__isnull=True).first()
        winners.append({"title": snapshot.title, "entry_public_id": entry.public_id if entry else None, "votes": row.votes})
    return winners


def public_projection(event):
    """Public block: the window while voting runs; the award only once published. Never a live count."""
    require_capability(event, PEOPLES_CHOICE)
    config, result = config_for(event), result_for(event)
    award = None if result is None else {"prize_name": result.prize_name, "total_votes": result.total_votes,
                                         "published_at": result.published_at, "winners": _public_winners(event, result)}
    return {"event_id": event.pk, "state": state(config, result), **window(config), "award": award}


def winning_snapshot_ids(event):
    """Gallery badges: the published winners only, and only while the capability is on."""
    if not enabled(event.makerspace, PEOPLES_CHOICE):
        return set()
    result = result_for(event)
    if result is None:
        return set()
    return set(result.standings.filter(winner=True).values_list("submission_snapshot_id", flat=True))
