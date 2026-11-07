"""The sole track/prize/round-definition writer. Round config freezes at open."""

from django.utils.translation import gettext
from django.http import Http404
from rest_framework.exceptions import ValidationError

from .boundary import audit, changed, command, envelope, mutation, owned
from .errors import invalid
from .models_definitions import HackathonPrize, HackathonTrack, JudgingCriterion, JudgingRound
from .pairwise_projection import require_pairwise
from .ports import runtime
from .serializers import PrizeInput, RoundInput, TrackInput, validated


def save_definition(event_id, *, actor, kind, data, object_id=None):
    model, serializer = {"tracks": (HackathonTrack, TrackInput), "prizes": (HackathonPrize, PrizeInput),
                         "judging-rounds": (JudgingRound, RoundInput)}[kind]
    values = validated(serializer, data, partial=object_id is not None)
    with mutation(event_id, actor) as (event, _):
        def run():
            payload = {key: value for key, value in values.items() if key not in ("operation_id", "expected_version")}
            criteria = payload.pop("criteria", None) if model is JudgingRound else None
            options = {key: payload.pop(key) for key in ("guidance", "exploration") if key in payload}
            panel = payload.pop("panel", None) if model is JudgingRound else None
            row = owned(model, event_id, object_id, expected=values["expected_version"]) if object_id else model(event=event)
            previous_mode = getattr(row, "mode", None) if object_id else None
            if not object_id and values["expected_version"] != 0:
                invalid("A new definition requires expected_version 0.")
            if model is JudgingRound and row.state != "draft":
                invalid("Open rounds are frozen. Create a new round to change its rubric.")
            _references(event, payload)
            if payload.get("submission_stage_id") is not None:  # #178: a stage of this event.
                from apps.events.submissions.models_stages import SubmissionStage
                if not SubmissionStage.objects.filter(event=event, pk=payload["submission_stage_id"]).exists():
                    raise Http404
            if model is JudgingRound and "pairwise" in (getattr(row, "mode", None), payload.get("mode")):
                require_pairwise(event, hide=False)
            for key, value in payload.items():
                setattr(row, key, value)
            if model is JudgingRound:
                criteria = _validate_round(row, criteria, options)
            if model is HackathonTrack and HackathonTrack.objects.filter(event=event, name=row.name).exclude(pk=row.pk).exists():
                raise ValidationError({"name": gettext("A track already uses this name.")})
            if object_id:
                changed(event, actor, "definition_updated", row)
                if previous_mode is not None and previous_mode != row.mode:
                    audit(event, actor, "round_mode_changed", row, version=row.version, previous=previous_mode, mode=row.mode)
            else:
                row.save()
                audit(event, actor, "definition_created", row, version=row.version)
            if panel is not None:
                from .round_settings import replace_panel
                replace_panel(event, row, panel)
            if criteria is not None:
                row.criteria.all().delete()
                for priority, criterion in enumerate(criteria):
                    JudgingCriterion.objects.create(round=row, priority=priority, **criterion)
            return envelope(row)
        return command(event, actor, values, path=f"{kind}/{object_id or ''}", run=run)


def _validate_round(row, criteria, options):
    """Mode rules. Returns the criteria to write ([] clears a rubric left over from another mode)."""
    if row.opens_at and row.closes_at and row.closes_at <= row.opens_at:
        raise ValidationError({"closes_at": gettext("The end must follow the start.")})
    if JudgingRound.objects.filter(event_id=row.event_id, key=row.key).exclude(pk=row.pk).exists():
        raise ValidationError({"key": gettext("This round key is already in use.")})
    existing = list(row.criteria.all()) if row.pk else []
    if row.mode == "weighted_1_5" and not (criteria or existing):
        raise ValidationError({"criteria": gettext("Provide an anchored weighted rubric.")})
    if row.mode in ("top3", "pairwise") and row.normalization != "none":
        raise ValidationError({"normalization": gettext("Z-score normalization is only available for weighted scoring.")})
    if row.mode != "pairwise":
        if options:
            raise ValidationError({key: "This setting applies to pairwise rounds only." for key in options})
        row.configuration = {}
        return criteria
    if criteria:
        raise ValidationError({"criteria": gettext("Pairwise rounds compare projects directly and use no rubric.")})
    # Draft-only pairwise settings; opening the round freezes them with the CrowdBT parameters.
    draft = {"guidance": row.configuration.get("guidance", ""),
             "pairwise": {"exploration": row.configuration.get("pairwise", {}).get("exploration", 0.1)}}
    if "guidance" in options:
        draft["guidance"] = options["guidance"]
    if "exploration" in options:
        draft["pairwise"]["exploration"] = float(options["exploration"])
    row.configuration = draft
    return [] if existing else None


def _references(event, payload):
    section_id = payload.get("website_section_id")
    if section_id:
        from apps.events.models_website import EventPageSection
        if not EventPageSection.objects.filter(pk=section_id, page__event_id=event.pk).exists():
            raise Http404
    track_id = payload.get("track_id")
    if track_id and not HackathonTrack.objects.filter(event=event, pk=track_id).exists():
        raise Http404
    sponsor_id = payload.get("sponsor_id")
    if sponsor_id:
        sponsor = runtime().sponsor(sponsor_id)
        if sponsor.event_id != event.pk or not sponsor.active:
            raise Http404
        track_id = payload.get("track_id")
        if track_id and track_id not in sponsor.track_ids:
            raise ValidationError({"sponsor_id": gettext("The sponsor must cover this prize's track.")})
