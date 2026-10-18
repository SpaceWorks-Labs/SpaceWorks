"""G's clone workflow delegates D definitions here; no participant state is copied."""

from copy import deepcopy

from django.http import Http404

from apps.events import event_authority
from .boundary import audit
from .models_definitions import HackathonPrize, HackathonTrack, JudgingCriterion, JudgingRound
from apps.events.programme_locks import assert_lock_context
from apps.events.contributions.models_roles import EventSponsor
from apps.makerspaces.resource_clone import bounded_children


def copy_definitions_locked(*, source_event_id, target_event, actor, sponsor_map, locks):
    """G holds sorted source/target event locks and the complete declared fences.

    C supplies copied EventSponsor IDs. Existing page-section IDs are cleared;
    pages' copy-on-write workflow owns any later matching section references.
    """
    assert_lock_context(locks)
    if target_event.pk != locks.event_id:
        raise Http404
    source = event_authority.get_event(actor, source_event_id, "edit_details")
    event_authority.require(actor, target_event, "edit_details")
    if source.makerspace_id != target_event.makerspace_id:
        raise Http404
    if HackathonTrack.objects.filter(event=target_event).exists() or JudgingRound.objects.filter(event=target_event).exists():
        from .errors import invalid
        invalid("Copy definitions into an empty new event.")
    tracks = {}
    for row in bounded_children(HackathonTrack.objects.filter(event=source).order_by("pk")):
        tracks[row.pk] = HackathonTrack.objects.create(event=target_event, name=row.name, description=row.description,
            criteria=deepcopy(row.criteria), form=deepcopy(row.form), eligibility_rules=deepcopy(row.eligibility_rules),
            capacity=row.capacity, order=row.order)
    for row in bounded_children(HackathonPrize.objects.filter(event=source).order_by("pk")):
        sponsor_id = sponsor_map.get(row.sponsor_id) if row.sponsor_id else None
        if row.sponsor_id and not sponsor_id:
            raise Http404
        if sponsor_id and not EventSponsor.objects.filter(pk=sponsor_id, event=target_event).exists():
            raise Http404
        HackathonPrize.objects.create(event=target_event, name=row.name, description=row.description,
            criteria=deepcopy(row.criteria), form=deepcopy(row.form), eligibility_rules=deepcopy(row.eligibility_rules),
            track=tracks.get(row.track_id), sponsor_id=sponsor_id, order=row.order, award_count=row.award_count,
            winner_selection_mode=row.winner_selection_mode if sponsor_id else "manager")
    count = 0
    for row in bounded_children(JudgingRound.objects.filter(event=source).order_by("pk")):
        target = JudgingRound.objects.create(event=target_event, key=row.key, mode=row.mode, min_reviews=row.min_reviews,
            normalization=row.normalization, minutes_per_view=row.minutes_per_view, judging_minutes=row.judging_minutes)
        for criterion in bounded_children(row.criteria.order_by("priority", "pk")):
            JudgingCriterion.objects.create(round=target, key=criterion.key, label=criterion.label,
                weight=criterion.weight, anchors=deepcopy(criterion.anchors), priority=criterion.priority)
        count += 1
    audit(target_event, actor, "judging_definitions_copied", target_event, tracks=len(tracks), rounds=count)
    return {key: value.pk for key, value in tracks.items()}
