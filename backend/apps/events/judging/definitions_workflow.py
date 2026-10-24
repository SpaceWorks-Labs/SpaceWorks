"""The sole track/prize/round-definition writer. Round config freezes at open."""

from django.http import Http404
from rest_framework.exceptions import ValidationError

from .boundary import audit, changed, command, envelope, mutation, owned
from .errors import invalid
from .models_definitions import HackathonPrize, HackathonTrack, JudgingCriterion, JudgingRound
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
            row = owned(model, event_id, object_id, expected=values["expected_version"]) if object_id else model(event=event)
            if not object_id and values["expected_version"] != 0:
                invalid("A new definition requires expected_version 0.")
            if model is JudgingRound and row.state != "draft":
                invalid("Open rounds are frozen. Create a new round to change its rubric.")
            _references(event, payload)
            for key, value in payload.items():
                setattr(row, key, value)
            if model is JudgingRound:
                _validate_round(row, criteria)
            if model is HackathonTrack and HackathonTrack.objects.filter(event=event, name=row.name).exclude(pk=row.pk).exists():
                raise ValidationError({"name": "A track already uses this name."})
            if object_id:
                changed(event, actor, "definition_updated", row)
            else:
                row.save()
                audit(event, actor, "definition_created", row, version=row.version)
            if criteria is not None:
                row.criteria.all().delete()
                for priority, criterion in enumerate(criteria):
                    JudgingCriterion.objects.create(round=row, priority=priority, **criterion)
            return envelope(row)
        return command(event, actor, values, path=f"{kind}/{object_id or ''}", run=run)


def _validate_round(row, criteria):
    if row.opens_at and row.closes_at and row.closes_at <= row.opens_at:
        raise ValidationError({"closes_at": "The end must follow the start."})
    if JudgingRound.objects.filter(event_id=row.event_id, key=row.key).exclude(pk=row.pk).exists():
        raise ValidationError({"key": "This round key is already in use."})
    existing = list(row.criteria.all()) if row.pk else []
    if row.mode == "weighted_1_5" and not (criteria or existing):
        raise ValidationError({"criteria": "Provide an anchored weighted rubric."})
    if row.mode == "top3" and row.normalization != "none":
        raise ValidationError({"normalization": "Z-score normalization is only available for weighted scoring."})


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
            raise ValidationError({"sponsor_id": "The sponsor must cover this prize's track."})
