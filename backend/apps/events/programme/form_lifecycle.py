"""Archive already encrypted source evidence without a late KMS operation."""
from apps.events.answer_derivations.models import EventAnswerDerivation
from apps.events.answer_derivations.subjects import subject_filter, resolve_subject
from apps.events.answer_derivations.workflow import require_locks, save_source, audit


def archive_sources_locked(*, subject, locks, archive_kind, archive_id):
    event = require_locks(subject, locks)
    parent = resolve_subject(subject, lock=True)
    for row in EventAnswerDerivation.objects.select_for_update().filter(**subject_filter(subject)):
        if not row.locked_at:
            continue
        from apps.encryption.preparation import prepared_keys
        from apps.events.answer_derivations.crypto import encrypt_source
        active, keys = prepared_keys(event.makerspace_id)
        reason = encrypt_source(f"{archive_kind}:{archive_id}", pk=row.pk,
            makerspace_id=event.makerspace_id, version=active.version, dek=keys[active.version], field="reopen_reason_envelope")
        row.source_history = [*row.source_history, {
            "source_dob_envelope": row.source_dob_envelope, "event_date_revision": row.event_date_revision,
            "as_of_date": row.as_of_date.isoformat(), "locked_at": row.locked_at.isoformat(),
            "version": row.version, "reason_envelope": reason,
        }]
        row.locked_at = None
        row.version += 1
        save_source(row, reopen=True)
        audit(None, "reopened", event, subject=subject, row=row, archive_kind=archive_kind, archive_id=archive_id)
    parent.answer_locked_at = None
    parent.date_review_required = True
    parent.save(update_fields=["answer_locked_at", "date_review_required"])
