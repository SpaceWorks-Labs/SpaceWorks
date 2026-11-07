"""B consumes D's track/prize rules under the submission event lock."""

from django.utils.translation import gettext
from django.http import Http404
from rest_framework.exceptions import ValidationError

from .boundary import assert_locked
from .models_definitions import HackathonPrize, HackathonTrack
from .ports import runtime


def require_selections_locked(*, event_id, team_id, track_ids, prize_ids, tech_tags, locks):
    assert_locked(locks)
    if event_id != locks.event_id:
        raise Http404
    tracks = {t.pk: t for t in HackathonTrack.objects.filter(event_id=event_id, pk__in=track_ids)}
    prizes = {p.pk: p for p in HackathonPrize.objects.filter(event_id=event_id, pk__in=prize_ids)}
    if set(tracks) != set(track_ids) or set(prizes) != set(prize_ids):
        raise Http404
    counts = runtime().track_occupancy_locked(event_id=event_id, track_ids=tuple(sorted(tracks)),
                                             exclude_team_id=team_id, locks=locks)
    if set(counts) != set(tracks) or any(type(value) is not int or value < 0 for value in counts.values()):
        from .errors import ProgrammeError
        raise ProgrammeError("programme_unavailable", "Track capacity is temporarily unavailable.", status=503)
    for track in tracks.values():
        _tags(track.eligibility_rules, tech_tags)
        if track.capacity and counts[track.pk] >= track.capacity:
            from .errors import ProgrammeError
            raise ProgrammeError("track_capacity_full", "This track has reached its project capacity.")
    for prize in prizes.values():
        _tags(prize.eligibility_rules, tech_tags)
        if prize.track_id and prize.track_id not in tracks:
            raise ValidationError({"prize_ids": gettext("Select the prize's track as well.")})
    return {"tracks": [{"id": t.pk, "version": t.version, "form": t.form} for t in tracks.values()],
            "prizes": [{"id": p.pk, "version": p.version, "form": p.form} for p in prizes.values()]}


def _tags(rules, tech_tags):
    if set(rules) - {"required_tech_tags"}:
        raise ValidationError({"prize_ids": gettext("Unsupported eligibility rules must be reviewed by the organizer.")})
    if not set(rules.get("required_tech_tags", ())) <= set(tech_tags):
        raise ValidationError({"track_ids": gettext("This project does not meet the chosen track or prize criteria.")})
