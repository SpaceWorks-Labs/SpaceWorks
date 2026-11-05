"""L21b finalists: preview, apply under the event lock, and publish once.

Finalists come from a FINALIZED round's live calculation, so a disqualified or withdrawn project (no
longer eligible or current) never advances. Applying writes an append-only advance into a DRAFT round;
that round then opens on the finalists alone. Results, awards and prizes come from the final round:
a round that advanced finalists can no longer be finalized into results.
"""

from django.http import Http404
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit.services import record
from .boundary import changed, command, digest, mutation, notice
from .errors import ProgrammeError, invalid, require_version
from .models_definitions import JudgingRound
from .models_finalists import FinalistAdvance, FinalistAnnouncement, JudgingFinalist
from .ports import runtime
from .projections import round_calculation
from .serializers import validated
from .serializers_l21b import FinalistApplyInput, FinalistPublishInput, FinalistSelection


def current_advance(round):
    return FinalistAdvance.objects.filter(target_round=round).order_by("-pk").first()


def current_finalist_ids(round):
    """Snapshot IDs a round judges, or None when no finalists were advanced into it."""
    advance = current_advance(round) if round.pk else None
    if advance is None:
        return None
    return set(advance.finalists.values_list("snapshot_id", flat=True))


def _rounds(event_id, values, *, lock=False):
    rows = JudgingRound.objects.select_for_update() if lock else JudgingRound.objects
    found = {r.pk: r for r in rows.filter(event_id=event_id, pk__in=(values["source_round_id"], values["target_round_id"]))}
    source, target = found.get(values["source_round_id"]), found.get(values["target_round_id"])
    if source is None or target is None:
        raise Http404
    if source.pk == target.pk:
        raise ValidationError({"target_round_id": "Choose a different round for the finalists."})
    if source.state != "finalized":
        invalid("Finalize the source round before advancing finalists.")
    if target.state != "draft":
        invalid("Finalists can only advance into a draft round.")
    ancestor = source
    while ancestor is not None:  # Never loop a project back into a round that fed its source.
        if ancestor.advanced_from_id == target.pk:
            invalid("That round already feeds the source round.")
        ancestor = ancestor.advanced_from
    return source, target


def ranked_rows(source):
    """A finalized round's reviewed projects, best first."""
    return sorted((r for r in round_calculation(source)["rows"] if r["n"]), key=lambda r: (r["rank"], r["snapshot_id"]))


def select_ranked(rows, *, selection, top_n=None, snapshot_ids=()):
    """Top N with every project tied at the cutoff, or a hand-picked subset. Shared with stage
    shortlists (#179). Returns (chosen rows, tied at cutoff)."""
    eligible = {r["snapshot_id"]: r for r in rows}
    if selection == "top_n":
        if not rows:
            return [], False
        cutoff = rows[min(top_n, len(rows)) - 1]["rank"]
        chosen = [r for r in rows if r["rank"] <= cutoff]  # A tie at the cutoff takes every tied project.
        return chosen, len(chosen) > top_n
    if any(pk not in eligible for pk in snapshot_ids):
        raise ValidationError({"snapshot_ids": "Pick only eligible, reviewed projects from the source round."})
    return [eligible[pk] for pk in snapshot_ids], False


def _plan(source, target, values):
    chosen, tied = select_ranked(ranked_rows(source), selection=values["selection"], top_n=values.get("top_n"),
                                 snapshot_ids=values.get("snapshot_ids", ()))
    finalists = [{"snapshot_id": r["snapshot_id"], "title": runtime().snapshot(r["snapshot_id"]).title,
                  "source_rank": r["rank"]} for r in chosen]
    fingerprint = digest({"source": [source.pk, source.version], "target": [target.pk, target.version],
                          "selection": values["selection"], "top_n": values.get("top_n"),
                          "snapshots": [f["snapshot_id"] for f in finalists]})
    return {"source_round_id": source.pk, "target_round_id": target.pk, "selection": values["selection"],
            "top_n": values.get("top_n"), "tied_at_cutoff": tied, "fingerprint": fingerprint, "finalists": finalists}


def preview(event_id, *, actor, params):
    from apps.events import event_authority
    from .feature import require_capability
    event = event_authority.get_event(actor, event_id, "manage_hackathon")
    runtime().require_programme(event)
    require_capability(event, "events.finalists")
    serializer = FinalistSelection(data=params)
    serializer.is_valid(raise_exception=True)
    source, target = _rounds(event_id, serializer.validated_data)
    return _plan(source, target, serializer.validated_data)


def apply(event_id, *, actor, data):
    values = validated(FinalistApplyInput, data)
    with mutation(event_id, actor) as (event, _):
        from .feature import require_capability
        require_capability(event, "events.finalists")

        def run():
            source, target = _rounds(event_id, values, lock=True)
            require_version(target, values["expected_version"])
            plan = _plan(source, target, values)
            if plan["fingerprint"] != values["fingerprint"]:
                raise ProgrammeError("plan_changed", "The finalists changed since the preview. Preview again.")
            if not plan["finalists"]:
                invalid("There are no eligible finalists to advance.")
            advance = FinalistAdvance.objects.create(event=event, source_round=source, target_round=target,
                selection=values["selection"], top_n=values.get("top_n"), fingerprint=plan["fingerprint"], created_by=actor)
            for row in plan["finalists"]:
                JudgingFinalist.objects.create(advance=advance, snapshot_id=row["snapshot_id"], source_rank=row["source_rank"])
            target.advanced_from = source
            changed(event, actor, "round_finalists_set", target)
            record(actor, "event.judging.finalists_advanced", makerspace=event.makerspace, target=advance,
                   meta={"event_id": event.pk, "round_id": target.pk, "count": len(plan["finalists"])})
            return {**plan, "id": advance.pk}
        return command(event, actor, values, path="finalists/apply", run=run)


def publish(event_id, *, actor, data):
    values = validated(FinalistPublishInput, data)
    with mutation(event_id, actor, permission=None) as (event, _):
        from .feature import require_capability
        require_capability(event, "events.finalists")

        def run():
            advance = FinalistAdvance.objects.select_related("target_round").filter(
                event=event, pk=values["advance_id"]).first()
            if advance is None:
                raise Http404
            require_version(advance.target_round, values["expected_version"])
            if current_advance(advance.target_round).pk != advance.pk:
                invalid("Publish the round's current finalists.")
            if FinalistAnnouncement.objects.filter(advance=advance).exists():
                raise ProgrammeError("already_published", "These finalists are already published.")
            for snapshot_id in advance.finalists.values_list("snapshot_id", flat=True):
                snapshot = runtime().snapshot(snapshot_id)
                if not snapshot.current or not snapshot.eligible:
                    invalid("A finalist is no longer eligible. Advance the finalists again.")
            row = FinalistAnnouncement.objects.create(event=event, advance=advance, published_at=timezone.now(),
                                                      published_by=actor)
            record(actor, "event.judging.finalists_published", makerspace=event.makerspace, target=row,
                   meta={"event_id": event.pk, "round_id": advance.target_round_id})
            from .options import option
            if option(event, "finalists_email"):
                notice(event, "finalists_announced", row.pk, 1)
            return {"id": advance.pk, "event_id": event.pk, "version": advance.target_round.version,
                    "state": "published", "allowed_actions": []}
        return command(event, actor, values, path="finalists/publish", run=run)


def projection(advance):
    current = current_advance(advance.target_round)
    announcement = FinalistAnnouncement.objects.filter(advance=advance).first()
    finalists = [{"snapshot_id": f.snapshot_id, "title": runtime().snapshot(f.snapshot_id).title,
                  "source_rank": f.source_rank} for f in advance.finalists.order_by("source_rank", "snapshot_id")]
    is_current = current is not None and current.pk == advance.pk
    return {"id": advance.pk, "event_id": advance.event_id, "source_round_id": advance.source_round_id,
            "target_round_id": advance.target_round_id, "selection": advance.selection, "top_n": advance.top_n,
            "created_at": advance.created_at, "current": is_current,
            "published_at": announcement.published_at if announcement else None, "finalists": finalists,
            "allowed_actions": ["publish"] if is_current and announcement is None else []}


def published_finalists(event):
    """Public block: the newest announcement's live, eligible finalists (gallery consent applied by the caller)."""
    announcement = FinalistAnnouncement.objects.filter(event=event).order_by("-published_at", "-pk").first()
    if announcement is None:
        return None, []
    snapshots = [runtime().snapshot(pk) for pk in announcement.advance.finalists.order_by(
        "source_rank", "snapshot_id").values_list("snapshot_id", flat=True)]
    return announcement, [s for s in snapshots if s.event_id == event.pk and s.current and s.eligible]


def member_is_published_finalist(*, event_id, member_id, advance_id, announcement_id):
    """Finalist certificates follow the publication: the member is in a published, still-eligible finalist."""
    announcement = FinalistAnnouncement.objects.filter(pk=announcement_id, event_id=event_id, advance_id=advance_id).first()
    if announcement is None:
        return False
    for snapshot_id in announcement.advance.finalists.values_list("snapshot_id", flat=True):
        snapshot = runtime().snapshot(snapshot_id)
        if snapshot.event_id == event_id and snapshot.current and snapshot.eligible and member_id in snapshot.member_ids:
            return True
    return False
