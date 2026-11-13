"""Resolve aware stage dates without changing admission or assignments."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from .policy import StagePolicyError


YEAR_SECONDS = 365 * 24 * 60 * 60


def _aware(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise StagePolicyError("stage_datetime_required")
    return value


def _seconds(value, *, positive=False):
    if type(value) is not int or not (1 if positive else -YEAR_SECONDS) <= value <= YEAR_SECONDS:
        raise StagePolicyError("invalid_stage_offset")
    return value


@dataclass(frozen=True, kw_only=True)
class Schedule:
    opens_at: datetime
    due_at: datetime


def resolve(*, triggered_at, event_start, event_end, opening_mode, due_mode,
            opens_at=None, opening_offset_seconds=None, due_at=None,
            due_after_seconds=None, due_event_offset_seconds=None):
    if not isinstance(opening_mode, str) or not isinstance(due_mode, str):
        raise StagePolicyError("invalid_stage_schedule")
    triggered_at, event_start, event_end = map(_aware, (triggered_at, event_start, event_end))
    if event_end < event_start:
        raise StagePolicyError("invalid_event_dates")
    if opening_mode == "trigger":
        if opens_at is not None or opening_offset_seconds is not None:
            raise StagePolicyError("invalid_stage_opening")
        opening = triggered_at
    elif opening_mode == "absolute":
        if opening_offset_seconds is not None:
            raise StagePolicyError("invalid_stage_opening")
        opening = _aware(opens_at)
    elif opening_mode in {"event_start", "event_end"}:
        if opens_at is not None:
            raise StagePolicyError("invalid_stage_opening")
        anchor = event_start if opening_mode == "event_start" else event_end
        opening = anchor + timedelta(seconds=_seconds(opening_offset_seconds))
    else:
        raise StagePolicyError("invalid_stage_opening")
    if due_mode == "absolute":
        if due_after_seconds is not None or due_event_offset_seconds is not None:
            raise StagePolicyError("invalid_stage_deadline")
        deadline = _aware(due_at)
    elif due_mode == "after_trigger":
        if due_at is not None or due_event_offset_seconds is not None:
            raise StagePolicyError("invalid_stage_deadline")
        deadline = triggered_at + timedelta(seconds=_seconds(due_after_seconds, positive=True))
    elif due_mode in {"event_start", "event_end"}:
        if due_at is not None or due_after_seconds is not None:
            raise StagePolicyError("invalid_stage_deadline")
        anchor = event_start if due_mode == "event_start" else event_end
        deadline = anchor + timedelta(seconds=_seconds(due_event_offset_seconds))
    else:
        raise StagePolicyError("invalid_stage_deadline")
    if opening >= deadline:
        raise StagePolicyError("stage_opening_not_before_due")
    return Schedule(opens_at=opening, due_at=deadline)


def reminder_times(*, triggered_at, due_at, offsets):
    triggered_at, due_at = _aware(triggered_at), _aware(due_at)
    if not isinstance(offsets, list) or len(offsets) > 10:
        raise StagePolicyError("invalid_reminder_offsets")
    for offset in offsets:
        _seconds(offset)
        if offset >= 0:
            raise StagePolicyError("invalid_reminder_offsets")
    if len(set(offsets)) != len(offsets):
        raise StagePolicyError("invalid_reminder_offsets")
    return tuple(sorted(when for offset in offsets
                        if (when := due_at + timedelta(seconds=offset)) > triggered_at))
