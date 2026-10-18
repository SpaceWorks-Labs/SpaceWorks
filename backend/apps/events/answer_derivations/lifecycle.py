"""Date changes, owner confirmation, freeze points, and immutable reopen history."""

from dataclasses import dataclass, field
from datetime import timedelta

from django.db import connection
from django.utils import timezone

from apps.events import event_authority
from apps.events.contracts.subjects import AnswerSubject, SubjectKind
from apps.events.models_event import Event

from .crypto import encrypt_source, prepared_key, require_preparation_boundary
from .dates import event_date, require_review, review_target
from .errors import DerivationError
from .models import EventAnswerDerivation
from .subjects import binding_for, require_owner, resolve_subject, subject_filter, subject_model
from .workflow import audit, require_event_locks, require_locks, save_source

_REOPEN_FACTORY = object()


def review_date_locked(*, actor_id, subject, revision, as_of_date, locks):
    event = require_locks(subject, locks)
    require_owner(actor_id, subject)
    source = resolve_subject(subject, lock=True)
    rows = list(EventAnswerDerivation.objects.select_for_update().filter(**subject_filter(subject)))
    target = review_target(event, rows)
    require_review(revision, as_of_date, target)
    for row in rows:
        if not row.locked_at:
            row.event_date_revision, row.as_of_date = target
            row.version += 1
            save_source(row)
    if rows:
        source.date_review_required = False
        source.version += 1
        source.save(update_fields=["date_review_required", "version"])
        audit(actor_id, "date_reviewed", event, subject=subject, date_revision=target[0])


def lock_subject_locked(*, actor_id, subject, locks, closing=False):
    """Close freezes even pending review; decisions must refuse pending review.

    A/G/C own decision/close authorization and call this after that check. A close
    does not change status, clear review, or move a queue position.
    """
    event = require_locks(subject, locks)
    source = resolve_subject(subject, lock=True)
    rows = list(EventAnswerDerivation.objects.select_for_update().filter(**subject_filter(subject)))
    pending = bool(getattr(source, "date_review_required", False)) or any(
        not row.locked_at and row.event_date_revision != event.event_date_revision for row in rows
    )
    if pending and not closing:
        raise DerivationError("date_review_required", "Owner date review is required.", status=409)
    now = timezone.now()
    changed = False
    for row in rows:
        if row.locked_at:
            continue
        row.event_date_revision, row.as_of_date = event.event_date_revision, event_date(event)
        row.locked_at = now
        row.version += 1
        save_source(row)
        changed = True
    if changed:
        source.answer_locked_at = now
        source.date_review_required = pending
        source.version += 1
        source.save(update_fields=["answer_locked_at", "date_review_required", "version"])
        audit(actor_id, "locked", event, subject=subject, closing=closing, date_revision=event.event_date_revision)


def date_changed_locked(*, event_id, actor_id, locks):
    """G calls after incrementing starts_at/timezone revision under event locks.

    Notices commit with the review flag and dispatch after commit. Bumping
    subject versions invalidates response ETags without storing a computed age.
    """
    event = require_event_locks(event_id, locks)
    from apps.events.programme_locks import assert_lock_context
    assert_lock_context(locks)
    owners = set()
    for kind in SubjectKind:
        ids = EventAnswerDerivation.objects.filter(
            event_id=event_id, locked_at__isnull=True,
        ).exclude(**{f"{kind.value}_id__isnull": True}).values_list(f"{kind.value}_id", flat=True)
        rows = subject_model(kind).objects.select_for_update().filter(
            pk__in=ids, event_id=event_id, member_id__isnull=False).order_by("pk")
        for row in rows:
            if row.member_id is not None and row.member_id not in locks.account_ids:
                raise RuntimeError("Declare every affected answer owner before event locks.")
            row.date_review_required = True
            row.version += 1
            row.save(update_fields=["date_review_required", "version"])
            if row.member_id:
                owners.add(row.member_id)
            audit(actor_id, "date_review_requested", event, subject=binding_for(row, kind), date_revision=event.event_date_revision)
            from apps.events.hackathons.admission_date_notices import enqueue_locked
            enqueue_locked(event=event, row=row, kind=kind)
    return tuple(sorted(owners))


@dataclass(frozen=True)
class PreparedReopen:
    subject: AnswerSubject
    actor_id: int
    versions: tuple
    reasons: tuple = field(repr=False)
    expires_at: object
    _factory: object = field(repr=False)

    def __post_init__(self):
        if self._factory is not _REOPEN_FACTORY:
            raise TypeError("Use prepare_reopen.")


def prepare_reopen(*, actor_id, subject, reason):
    require_preparation_boundary()
    from apps.accounts.models import User

    source = resolve_subject(subject)
    event_authority.require(User.objects.get(pk=actor_id), source.event, None)
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
        raise DerivationError("reopen_reason_required", "Provide a bounded reopening reason.")
    version, dek = prepared_key(source.event.makerspace_id)
    rows = list(EventAnswerDerivation.objects.filter(**subject_filter(subject), locked_at__isnull=False))
    reasons = tuple((row.pk, encrypt_source(
        reason.strip(), pk=row.pk, makerspace_id=source.event.makerspace_id,
        version=version, dek=dek, field="reopen_reason_envelope",
    )) for row in rows)
    return PreparedReopen(subject, actor_id, tuple((row.pk, row.version) for row in rows), reasons,
                          timezone.now() + timedelta(seconds=60), _REOPEN_FACTORY)


def reopen_subject_locked(prepared, *, actor_id, subject, locks):
    event = require_locks(subject, locks)
    from apps.accounts.models import User

    event_authority.require(User.objects.get(pk=actor_id), event, None)
    if (not isinstance(prepared, PreparedReopen) or prepared.subject != subject
            or prepared.actor_id != actor_id or prepared.expires_at <= timezone.now()):
        raise DerivationError("save_preparation_expired", "Reopening preparation expired.", status=409)
    source = resolve_subject(subject, lock=True)
    rows = list(EventAnswerDerivation.objects.select_for_update().filter(**subject_filter(subject), locked_at__isnull=False))
    if {(row.pk, row.version) for row in rows} != set(prepared.versions):
        raise DerivationError("stale_version", "Answer source changed; review again.", status=409)
    reasons = dict(prepared.reasons)
    for row in rows:
        row.source_history = [*row.source_history, {
            "source_dob_envelope": row.source_dob_envelope, "event_date_revision": row.event_date_revision,
            "as_of_date": row.as_of_date.isoformat(), "locked_at": row.locked_at.isoformat(),
            "version": row.version, "reason_envelope": reasons[row.pk],
        }]
        row.locked_at = None
        row.event_date_revision, row.as_of_date = event.event_date_revision, event_date(event)
        row.version += 1
        save_source(row, reopen=True)
        audit(actor_id, "reopened", event, subject=subject, row=row, source_version=row.version)
    if rows:
        source.answer_locked_at = None
        source.date_review_required = True
        source.version += 1
        source.save(update_fields=["answer_locked_at", "date_review_required", "version"])
