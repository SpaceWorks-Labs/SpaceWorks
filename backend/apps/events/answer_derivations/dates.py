"""Event-local start and frozen answer-review dates."""

from datetime import date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .errors import DerivationError


def event_date(event):
    try:
        return event.starts_at.astimezone(ZoneInfo(event.timezone_name)).date()
    except (ValueError, ZoneInfoNotFoundError) as exc:
        raise DerivationError("event_timezone_unavailable", "Event timezone unavailable.", status=503) from exc


def review_target(event, rows=()):
    locked = [row for row in rows if row.locked_at is not None]
    if locked:
        targets = {(row.event_date_revision, row.as_of_date) for row in locked}
        if len(targets) != 1:
            raise DerivationError("answer_revision_conflict", "Answer revision requires review.", status=409)
        return targets.pop()
    return event.event_date_revision, event_date(event)


def require_review(revision, as_of_date, target):
    current_revision, current_date = target
    if type(as_of_date) is str:
        try:
            as_of_date = date.fromisoformat(as_of_date)
        except ValueError:
            as_of_date = None
    if type(revision) is not int or revision != current_revision or as_of_date != current_date:
        raise DerivationError(
            "event_date_changed", "Review age at the revised event start.", status=409,
            event_date_revision=current_revision, as_of_date=current_date.isoformat(),
        )
