"""Private attention and generosity diagnostics; no selection or public ranking."""
import json
import math
from datetime import timedelta
from statistics import mean, pstdev
from django.db.models import Count
from django.utils import timezone
from apps.events.contributions.ports import ports
from .models_rounds import MentorRound, MentorRoundCheckin, MentorRoundLock
from .models_queue import MentorProfile


def generosity(values):
    """Small/constant samples report no z score. Stable ID ordering is not ranking."""
    eligible = {key: rows for key, rows in values.items() if len(rows) >= 3}
    means = [mean(rows) for rows in eligible.values()]
    center = mean(means) if means else None
    deviation = pstdev(means) if len(means) >= 2 else 0
    return [{"mentor_assignment_id": key, "n": len(rows), "mean": round(mean(rows), 3) if rows else None,
        "z_score": round((mean(rows) - center) / deviation, 3) if key in eligible and deviation > 0 else None}
        for key, rows in sorted(values.items())]


def project(*, event, mentor_id=None):
    now = timezone.now()
    rounds = MentorRound.objects.filter(event=event, practice_run_id__isnull=True).order_by("index", "pk")
    checks = MentorRoundCheckin.objects.filter(event=event, round__practice_run_id__isnull=True)
    leases = MentorRoundLock.objects.filter(event=event, round__practice_run_id__isnull=True)
    if mentor_id:
        checks, leases = checks.filter(mentor_id=mentor_id), leases.filter(mentor_id=mentor_id)
    total = len(ports().teams.ids(event_id=event.pk, practice_run_id=None))
    per_round = [{"round_id": row.pk, "completed": checks.filter(round=row).count(),
        "remaining": max(0, total - checks.filter(round=row).count()) if mentor_id is None else None}
        for row in rounds]
    attention = []
    if mentor_id is None:
        away = checks.filter(away=True).values("team_id").annotate(n=Count("pk")).filter(n__gte=2)
        attention = [{"team_id": row["team_id"], "reason": "away_twice", "count": row["n"]} for row in away]
    profiles = MentorProfile.objects.filter(event=event, assignment__state="approved", assignment__imported_inert=False)
    if mentor_id:
        profiles = profiles.filter(assignment_id=mentor_id)
    nudges = []
    from .policy import in_windows
    active = 0
    for profile in profiles.select_related("assignment"):
        if not in_windows(profile.availability or profile.assignment.availability, now):
            continue
        active += 1
        visiting = leases.filter(mentor_id=profile.assignment_id, expires_at__gt=now).order_by("started_at").first()
        last = checks.filter(mentor_id=profile.assignment_id).order_by("-submitted_at").first()
        if visiting:
            minutes = int((now - visiting.started_at).total_seconds() // 60)
            if minutes >= 15:
                nudges.append({"mentor_assignment_id": profile.assignment_id, "reason": "long_visit", "minutes": minutes})
        elif last:
            minutes = int((now - last.submitted_at).total_seconds() // 60)
            if minutes >= 10:
                nudges.append({"mentor_assignment_id": profile.assignment_id,
                    "reason": "quiet" if minutes >= 20 else "check_in_due", "minutes": minutes})
    ratings = {}
    if mentor_id is None:
        for check in checks.select_related("round"):
            answers = json.loads(check.answers)
            values = [answers[key] for key in check.round.rating_keys if key in answers and
                type(answers[key]) in (int, float) and math.isfinite(answers[key])]
            ratings.setdefault(check.mentor_id, []).extend(values)
    return {"per_round": per_round, "active_mentors": active, "attention": attention,
            "nudges": nudges, "generosity": generosity(ratings) if mentor_id is None else []}
