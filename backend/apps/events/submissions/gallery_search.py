"""L21b public gallery search (X54): text search, sort, an award-winners filter and award badges.

Everything runs server-side over the same publishable entries the gallery already shows (live
consent, current and eligible snapshots). Awards come ONLY from the currently announced result and
only for awards the team asked to show publicly, so nothing reveals a winner before publication:
before it, `sort=awards` is the newest-first order, `awards=only` is empty and no entry has a badge.
"""

from django.db.models.functions import Lower
from django.http import Http404
from rest_framework.exceptions import ValidationError

from apps.events.judging.models_results import ResultPublicationState

SORTS = ("newest", "az", "awards")
PARAMS = frozenset({"q", "sort", "awards", "page"})


def published_awards(event):
    """``{snapshot_id: [{prize, rank}]}`` for the announced result's public awards, else ``{}``."""
    from .gallery_models import GalleryConsent
    from apps.events.judging.ports import runtime
    state = ResultPublicationState.objects.filter(event=event).select_related("current_announcement__result").first()
    if state is None or not state.current_announcement_id:
        return {}
    badges = {}
    for award in state.current_announcement.result.awards.filter(public_requested=True).order_by("prize_id", "rank"):
        snapshot = runtime().snapshot(award.submission_snapshot_id)
        if (snapshot.current and snapshot.eligible and snapshot.event_id == event.pk and GalleryConsent.objects.filter(
                event=event, snapshot_id=snapshot.id, metadata_public=True).exists()):
            badges.setdefault(snapshot.id, []).append({"prize": award.prize_name, "rank": award.rank})
    return badges


def query(event, rows, params):
    """Filter and order the gallery queryset; returns ``(rows, badges)``."""
    from apps.events.judging.feature import GALLERY_SEARCH, enabled
    used = {key for key in params if key != "page"}
    if not enabled(event.makerspace, GALLERY_SEARCH):
        if used:
            raise Http404  # Off: the search surface does not exist; the plain gallery still does.
        return rows.order_by("pk"), {}
    if set(params) - PARAMS:
        raise ValidationError({key: "Unknown gallery filter." for key in sorted(set(params) - PARAMS)})
    sort = params.get("sort") or "newest"
    if sort not in SORTS:
        raise ValidationError({"sort": "Use newest, az or awards."})
    text = (params.get("q") or "").strip()[:100]
    if text:
        rows = rows.filter(title__icontains=text) | rows.filter(description__icontains=text)
    badges = published_awards(event)
    if params.get("awards") == "only":
        rows = rows.filter(snapshot_id__in=list(badges))
    elif params.get("awards") not in (None, ""):
        raise ValidationError({"awards": "Use awards=only."})
    if sort == "az":
        rows = rows.order_by(Lower("title"), "pk")
    else:
        rows = rows.order_by("-snapshot__submitted_at", "-pk")
    if sort == "awards" and badges:
        ordered = list(rows)
        best = {pk: min(b["rank"] for b in values) for pk, values in badges.items()}
        ordered.sort(key=lambda row: (row.snapshot_id not in best, best.get(row.snapshot_id, 0)))
        return ordered, badges
    return rows, badges
