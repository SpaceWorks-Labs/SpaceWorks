"""L21b (X40): the five filterable staff event lists, one spec each.

A spec names the event permission that opens it, its allow-listed filters and its columns, and yields
rows in a stable keyset order. The JSON list and the CSV export both read `rows(...)`, so an export
holds exactly the rows the filtered list shows. Guest rows carry PII and are masked (lists) or refused
(exports) for a superadmin without a PII window.
"""

from dataclasses import dataclass

CHUNK = 500


@dataclass(frozen=True)
class Spec:
    key: str
    permission: str
    filters: frozenset
    columns: tuple
    pii: tuple = ()
    extra_columns: object = None  # callable(event) -> ((key, header), ...): columns that depend on the event


def _search(params):
    return (params.get("q") or "").strip().lower()


def _guests(event, params):
    from . import staff_list_guests
    from .models_registration import EventRegistration
    rows = EventRegistration.objects.filter(event=event).select_related("ticket_type").order_by("pk")
    if params.get("status"):
        rows = rows.filter(status=params["status"])
    rows = staff_list_guests.filter_rows(event, rows, params)
    extra, query, last = staff_list_guests.list_columns(event), _search(params), 0
    while True:  # Names are encrypted at rest, so the search runs per keyset chunk.
        chunk = list(rows.filter(pk__gt=last)[:CHUNK])
        if not chunk:
            return
        for row, reply, extras in staff_list_guests.annotate(event, chunk, extra):
            if query and query not in f"{row.name} {row.email}".lower():
                continue
            yield {"id": row.pk, "name": row.name, "email": row.email, "phone": row.phone, "status": row.status,
                   "ticket": row.ticket_type.name if row.ticket_type_id else "", "registered_at": row.created_at,
                   "reply": reply, **extras}
        last = chunk[-1].pk


def _guest_extra(event):
    from .staff_list_guests import list_columns
    return tuple(label for _id, label in list_columns(event))


def _teams(event, params):
    from django.db.models import Count, Q
    from .hackathons.team_models import HackathonTeam
    rows = HackathonTeam.objects.filter(event=event).annotate(
        members=Count("memberships", filter=Q(memberships__state="active"))).order_by("pk")
    if params.get("state"):
        rows = rows.filter(state=params["state"])
    if _search(params):
        rows = rows.filter(normalized_name__contains=_search(params))
    yield from _keyset(rows, lambda t: {"id": t.pk, "name": t.name, "state": t.state, "members": t.members,
                                         "eligibility_issue": t.eligibility_issue, "locked_at": t.locked_at})


def _submissions(event, params):
    from .submissions.models_projects import HackathonSubmission
    rows = HackathonSubmission.objects.filter(event=event).order_by("pk")
    for key in ("state", "triage"):
        if params.get(key):
            rows = rows.filter(**{key: params[key]})
    if _search(params):
        rows = rows.filter(title__icontains=_search(params))
    yield from _keyset(rows, lambda s: {"id": s.pk, "team_id": s.team_id, "title": s.title, "state": s.state,
                                         "triage": s.triage, "submitted_at": s.submitted_at})


def _results(event, params):
    from .judging.models_results import EventResultRevision, ResultPublicationState
    from .judging.ports import runtime
    latest = EventResultRevision.objects.filter(event=event).order_by("-version").first()
    if latest is None:
        return
    published = ResultPublicationState.objects.filter(event=event, current_announcement__result=latest).exists()
    rows = latest.awards.order_by("pk")
    if params.get("prize"):
        rows = rows.filter(prize_id=params["prize"])
    text = (params.get("q") or "").strip().casefold()  # E-B4 (D13): the results search matches project or prize.
    for row in _keyset(rows, lambda a: {"id": a.pk, "prize": a.prize_name, "rank": a.rank,
                                         "title": runtime().snapshot(a.submission_snapshot_id).title,
                                         "version": latest.version, "published": published}):
        if not text or text in row["title"].casefold() or text in row["prize"].casefold():
            yield row


def _progress(event, params):
    from .judging.models_definitions import JudgingRound
    from .judging.ports import runtime
    from .judging.projections import round_calculation
    rounds = JudgingRound.objects.filter(event=event).exclude(state="draft").order_by("pk")
    if params.get("round"):
        rounds = rounds.filter(pk=params["round"])
    for round in rounds:
        reviews = {row["snapshot_id"]: row["n"] for row in round_calculation(round)["rows"]}
        for snapshot_id in round.projects.order_by("snapshot_id").values_list("snapshot_id", flat=True):
            count = reviews.get(snapshot_id, 0)
            if params.get("below_target") == "true" and count >= round.min_reviews:
                continue
            yield {"id": f"{round.pk}:{snapshot_id}", "round": round.key, "title": runtime().snapshot(snapshot_id).title,
                   "reviews": count, "target": round.min_reviews}


def _keyset(rows, project):
    last = 0
    while True:
        chunk = list(rows.filter(pk__gt=last)[:CHUNK])
        if not chunk:
            return
        for row in chunk:
            yield project(row)
        last = chunk[-1].pk


SPECS = {
    "guests": (Spec("guests", "manage_registrations", frozenset({"status", "q", "reply", "list", "collected"}),
                    ("id", "name", "email", "phone", "status", "ticket", "registered_at", "reply"),
                    ("name", "email", "phone"),
                    _guest_extra),
               _guests),
    "teams": (Spec("teams", "manage_team", frozenset({"state", "q"}),
                   ("id", "name", "state", "members", "eligibility_issue", "locked_at")), _teams),
    "submissions": (Spec("submissions", "manage_hackathon", frozenset({"state", "triage", "q"}),
                         ("id", "team_id", "title", "state", "triage", "submitted_at")), _submissions),
    "results": (Spec("results", "manage_hackathon", frozenset({"prize", "q"}),
                     ("id", "prize", "rank", "title", "version", "published")), _results),
    "progress": (Spec("progress", "manage_hackathon", frozenset({"round", "below_target"}),
                      ("id", "round", "title", "reviews", "target")), _progress),
}
