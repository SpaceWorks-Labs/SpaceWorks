"""Derived visit states; lease secrets and prior ratings never enter other cards."""
from django.utils import timezone
from apps.events.contributions.ports import ports
from . import policy
from .analytics import prior_notes, stable_due_order
from .models_rounds import MentorRoundCheckin, MentorRoundLock, MentorConflict
from .projections import lease


def project(*, actor, event, round):
    mentor, _ = policy.mentor_for(actor, event)
    team_ids = ports().teams.ids(event_id=event.pk,
        practice_run_id=str(round.practice_run_id) if round.practice_run_id else None)
    completed = set(MentorRoundCheckin.objects.filter(round=round).values_list("team_id", flat=True))
    seen = set(MentorRoundCheckin.objects.filter(event=event, mentor=mentor,
        round__practice_run_id=round.practice_run_id).values_list("team_id", flat=True))
    conflicted = set(MentorConflict.objects.filter(mentor=mentor, active=True,
        kind__in=["declared", "affiliation"]).values_list("team_id", flat=True))
    leases = {row.team_id: row for row in MentorRoundLock.objects.filter(round=round, expires_at__gt=timezone.now())}
    cards = []
    for team_id in team_ids:
        own_team = mentor.member_id in ports().teams.member_ids(event_id=event.pk, team_id=team_id)
        current = leases.get(team_id)
        state = "done" if team_id in completed else "conflict" if own_team or team_id in conflicted else (
            "busy" if current else "seen" if team_id in seen else "due")
        cards.append({"team_id": team_id, "team_alias": ports().teams.alias(event_id=event.pk, team_id=team_id),
            "visit_state": state, "lease": lease(current) if current and current.mentor_id == mentor.pk else None,
            "prior_notes": prior_notes(event_id=event.pk, team_id=team_id,
                practice_run_id=round.practice_run_id) if state not in ("conflict", "busy") or (current and current.mentor_id == mentor.pk) else []})
    return {"teams": cards, "next_team_ids": stable_due_order([x["team_id"] for x in cards if x["visit_state"] == "due"],
        event_id=event.pk, round_id=round.pk, mentor_id=mentor.pk)}
