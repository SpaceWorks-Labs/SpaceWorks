"""Insert prepared ciphertext inside the caller's ordered event transaction."""

import hmac

from django.db import connection
from django.utils import timezone

from apps.audit.services import record
from apps.encryption.models import MakerspaceEncryptionKey
from apps.encryption.write_fence import PiiWriteFenced, assert_mapped_write_allowed
from apps.events.contracts.providers import LockedContext
from apps.events.models_event import Event

from .dates import require_review, review_target
from .errors import DerivationError, pii_unavailable
from .fences import require_owner_fence
from .models import EventAnswerDerivation
from .preparation import PreparedDerivations
from .subjects import require_owner, resolve_subject, subject_filter


def require_event_locks(event_id, locks):
    if (not connection.in_atomic_block or not isinstance(locks, LockedContext)
            or locks.event_id != event_id):
        raise RuntimeError("Use the ordered event workflow transaction.")
    event = Event.objects.get(pk=event_id)
    if event.makerspace_id not in locks.tenant_ids:
        raise RuntimeError("Declare the host source/write fence before event locks.")
    try:
        assert_mapped_write_allowed(event.makerspace_id)
    except PiiWriteFenced as exc:
        raise pii_unavailable() from exc
    return event


def require_locks(subject, locks):
    return require_event_locks(subject.event_id, locks)


def audit(actor_id, action, event, *, subject, row=None, **metadata):
    from apps.accounts.models import User

    record(
        User.objects.get(pk=actor_id) if actor_id is not None else None,
        f"events.answers.{action}", makerspace=event.makerspace, target=row,
        meta={"event_id": event.pk, "subject_kind": subject.kind.value,
              "subject_id": subject.subject_id, **metadata},
    )


def save_source(row, *, reopen=False):
    row._workflow_write = True
    row._workflow_reopen = reopen
    try:
        row.save(force_insert=row._state.adding)
    finally:
        row._workflow_write = False
        row._workflow_reopen = False


def insert_prepared_locked(
    prepared, *, actor_id, subject, locks, form_sha256, canonical_answer_sha256,
    creation_operation_id=None,
):
    """Return canonical descriptors only. No account/key row lock or broker I/O.

    The aggregate must check its operation receipt before preparation, validate
    the live F form hashes again, and persist the returned descriptors within the
    same transaction. Every source, including no-save and inline DOB, requires
    account_fences(owner IDs, tenant IDs) before event locks. A new subject needs
    the matching creation operation.
    """
    if prepared is None:
        return []
    if not isinstance(prepared, PreparedDerivations):
        raise TypeError("Use in-process prepared derivations.")
    require_owner_fence(subject, locks)
    event = require_locks(subject, locks)
    require_owner(actor_id, subject)
    binding = prepared.subject
    same_identity = (binding.event_id == subject.event_id
                     and binding.owner_member_id == subject.owner_member_id
                     and binding.kind == subject.kind)
    if not same_identity or (
        binding.subject_id != subject.subject_id if binding.subject_id is not None
        else binding.creation_operation_id != creation_operation_id
    ):
        raise DerivationError("invalid_preparation", "Prepared source belongs to another operation.")
    if prepared.expires_at <= timezone.now():
        raise DerivationError("save_preparation_expired", "Save preparation expired.", status=409)
    if event.makerspace_id != prepared.makerspace_id or not all(
        isinstance(current, str) and hmac.compare_digest(current, expected)
        for current, expected in ((form_sha256, prepared.form_sha256),
                                  (canonical_answer_sha256, prepared.canonical_answer_sha256))
    ):
        raise DerivationError("form_revision_changed", "Review the current event form.", status=409)
    # Fences precede domain locks in the outer service; this rechecks persistent
    # state in this transaction. It never tries to acquire an account/key row.
    try:
        assert_mapped_write_allowed(event.makerspace_id)
    except PiiWriteFenced as exc:
        raise pii_unavailable() from exc
    from django.conf import settings
    if not settings.PII_ENCRYPTION_ENABLED:
        raise pii_unavailable()
    if not MakerspaceEncryptionKey.objects.filter(
        makerspace_id=event.makerspace_id, version=prepared.key_version, status="active",
    ).exists():
        raise DerivationError("event_key_changed", "Protected-data key changed; review again.", status=409)
    subject_row = resolve_subject(subject, lock=True)
    rows = list(EventAnswerDerivation.objects.select_for_update().filter(**subject_filter(subject)))
    require_review(prepared.event_date_revision, prepared.as_of_date, review_target(event, rows))
    existing = {row.question_id: row for row in rows}
    result = []
    for source in prepared.sources:
        row = existing.get(source.question_id)
        if (row is None and source.base_version != 0) or (row is not None and (
            row.pk != source.pk or row.version != source.base_version or row.locked_at
        )):
            raise DerivationError("stale_version", "Answer source changed; review again.", status=409)
        if row is None:
            row = EventAnswerDerivation(
                pk=source.pk, question_id=source.question_id, **subject_filter(subject),
            )
        else:
            row.version += 1
        row.source_dob_envelope = source.envelope
        row.event_date_revision, row.as_of_date = prepared.event_date_revision, prepared.as_of_date
        save_source(row)
        audit(actor_id, "source_saved", event, subject=subject, row=row, source_version=row.version)
        result.append({"id": row.question_id, "type": "age_at_event", "derivation_id": row.pk})
    if rows or result:
        subject_row.date_review_required = False
        subject_row.save(update_fields=["date_review_required"])
    return result


def delete_draft_sources_locked(*, actor_id, subject, locks, question_ids=None):
    event = require_locks(subject, locks)
    require_owner(actor_id, subject)
    source = resolve_subject(subject, lock=True)
    if getattr(source, "state", None) != "draft":
        raise DerivationError("answers_retained", "Submitted evidence follows event retention.", status=409)
    rows = EventAnswerDerivation.objects.select_for_update().filter(**subject_filter(subject))
    if question_ids is not None:
        rows = rows.filter(question_id__in=question_ids)
    rows = list(rows)
    if any(row.locked_at or row.source_history for row in rows):
        raise DerivationError("answers_locked", "Submitted source evidence is retained.", status=409)
    for row in rows:
        audit(actor_id, "draft_source_deleted", event, subject=subject, row=row)
        row.delete()


def purge_event_sources_locked(*, event_id, actor_id=None):
    """Internal retention adapter: G authorizes source closure and orders purge."""
    if not connection.in_atomic_block:
        raise RuntimeError("Purge within the event retention transaction.")
    from apps.accounts.models import User

    event = Event.objects.get(pk=event_id)
    rows = EventAnswerDerivation.objects.filter(event_id=event_id)
    count = rows.count()
    if count:
        record(
            User.objects.get(pk=actor_id) if actor_id is not None else None,
            "events.answers.purged", makerspace=event.makerspace,
            meta={"event_id": event_id, "source_count": count},
        )
    return rows.delete()


def erase_owner_drafts_locked(*, owner_member_id, event_id, locks, actor_id=None):
    """G's authorized account-erasure adapter, before account-only key deletion.

    Submission/lock history remains tenant evidence. Typed parent services own
    later User-edge pseudonymization; this method never locks an account row.
    """
    from apps.events.contracts.subjects import SubjectKind
    from .subjects import binding_for, subject_model

    event = require_event_locks(event_id, locks)
    deleted = 0
    for kind in (SubjectKind.APPLICATION, SubjectKind.ROLE_ASSIGNMENT):
        parents = subject_model(kind).objects.select_for_update().filter(
            event_id=event_id, member_id=owner_member_id, state="draft",
        )
        for parent in parents:
            if any(getattr(parent, name, None) is not None for name in (
                "submitted_at", "applied_at", "answer_locked_at",
            )):
                continue
            subject = binding_for(parent, kind)
            rows = EventAnswerDerivation.objects.select_for_update().filter(
                **subject_filter(subject), locked_at__isnull=True, source_history=[],
            )
            for row in rows:
                audit(actor_id, "draft_source_erased", event, subject=subject, row=row)
                row.delete()
                deleted += 1
    return deleted
