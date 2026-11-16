"""Derived, space-verified achievements (decisions 302c, 303c, 304c). Computed live, never stored.

Two tiers, because the data has two privacy tiers:

* **Published hackathon results from ANY space** (judged awards and People's choice wins). They
  are already public, so they may appear whatever spaces the person belongs to. They follow the
  latest publication: a correction publishes a new revision and the pointer moves, a withdrawal
  clears the pointer, so a withdrawn or superseded award disappears with no cleanup here.
* **Crew roles, speaking and attendance: only spaces where the person is an active member**
  (`account_profile_spaces.listed_space_ids`), and only for public, listed, live events.

Rows are structured (kind, rank, prize, role, event, space, date) and the UI turns them into
translated sentences, so the server never bakes English into a payload.
"""

from django.utils import timezone

from .account_profile_activity import attended_events, event_is_public
from .account_profile_spaces import listed_space_ids

CREW_ROLES = ("co_organizer", "volunteer", "mentor", "judge")
DERIVED_LIMIT = 60


def _row(kind, event, when, **extra):
    return {"kind": kind, "event_title": event.title, "verified_by": event.makerspace.name,
            "occurred_on": when.date().isoformat() if hasattr(when, "date") else str(when), **extra}


def _own_snapshot_ids(user):
    from apps.events.models import SubmissionSnapshot
    return SubmissionSnapshot.objects.filter(sealed_member_ids__contains=[user.pk]).values("pk")


def _awards(user):
    from apps.events.judging.models_results import EventAward, ResultPublicationState
    current = ResultPublicationState.objects.filter(
        current_announcement__isnull=False).values("current_announcement__result_id")
    rows = EventAward.objects.filter(
        result_id__in=current, submission_snapshot_id__in=_own_snapshot_ids(user),
    ).select_related("prize", "result__event__makerspace", "result__announcement")
    for award in rows:
        event = award.result.event
        if event_is_public(event):
            yield _row("award", event, award.result.announcement.published_at,
                       rank=award.rank, prize_name=award.prize_name)


def _peoples_choice(user):
    from apps.events.judging.models_peoples_choice import PeoplesChoiceStanding
    rows = PeoplesChoiceStanding.objects.filter(
        winner=True, submission_snapshot_id__in=_own_snapshot_ids(user),
    ).select_related("result__event__makerspace")
    for standing in rows:
        event = standing.result.event
        if event_is_public(event):
            yield _row("peoples_choice", event, standing.result.published_at,
                       rank=1, prize_name=standing.result.prize_name)


def _roles(user, space_ids):
    from apps.events.contributions.models_roles import EventRoleAssignment
    rows = EventRoleAssignment.objects.filter(
        member=user, role__in=CREW_ROLES, imported_inert=False,
        state__in=("approved", "completed"), event__makerspace_id__in=space_ids,
        event__starts_at__lte=timezone.now(),
    ).select_related("event__makerspace")
    for assignment in rows:
        if event_is_public(assignment.event):
            yield _row("role", assignment.event, assignment.event.starts_at, role=assignment.role)


def _speaking(user, space_ids):
    try:
        from apps.events.speaker_history import contributions_for
    except (ImportError, AttributeError):
        return
    from .models import Makerspace
    now = timezone.now()
    for space in Makerspace.objects.filter(pk__in=space_ids):
        try:
            rows = list(contributions_for(user, space))
        except (ImportError, AttributeError):
            continue
        for row in rows:
            if row.occurred_at <= now and event_is_public(row.event):
                yield _row("speaker", row.event, row.occurred_at)


def derived_achievements(user):
    """Every verified row this person could show, newest first. Callers gate on the switch."""
    space_ids = listed_space_ids(user)
    rows = [*_awards(user), *_peoples_choice(user), *_roles(user, space_ids), *_speaking(user, space_ids)]
    attended = attended_events(user)["count"]
    if attended:
        rows.append({"kind": "attended", "count": attended, "verified_by": "", "event_title": "",
                     "occurred_on": ""})
    rows.sort(key=lambda row: row["occurred_on"], reverse=True)
    return rows[:DERIVED_LIMIT]


def _https(url):
    """SECURITY-REVIEW L-F1: filter on READ too -- a row that skipped the write serializer (tenant
    import, a /control/ edit) must never reach a reader's `href` with another scheme or credentials."""
    from urllib.parse import urlsplit

    try:
        parts = urlsplit(url or "")
    except ValueError:
        return ""
    return url if parts.scheme == "https" and parts.hostname and not parts.username and not parts.password else ""


def self_reported(profile):
    return [{"id": row.pk, "title": row.title, "issuer": row.issuer, "achieved_on": row.achieved_on,
             "url": _https(row.url), "description": row.description, "order": row.order}
            for row in profile.achievements.all()]


def achievements(profile):
    return {"verified": derived_achievements(profile.user), "self_reported": self_reported(profile)}
