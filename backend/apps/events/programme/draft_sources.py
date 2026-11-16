"""Owner edits and authorized form definition removal minimize unused draft DOB."""
import json

from apps.events.contracts.subjects import SubjectKind
from apps.events.answer_derivations.models import EventAnswerDerivation
from apps.events.answer_derivations.subjects import binding_for, resolve_subject, subject_filter, subject_model
from apps.events.answer_derivations.workflow import delete_draft_sources_locked
from apps.events.programme_locks import assert_lock_context


def _draft(parent):
    return (getattr(parent, "state", None) == "draft" and not parent.answer_locked_at
            and not any(getattr(parent, name, None) for name in ("submitted_at", "applied_at")))


def prune_answer_sources_locked(*, subject, snapshot, locks, audit_actor_id=None):
    """Caller already authorized this owner edit or this form definition change.

    Submitted/history-bearing sources are never deletion candidates, even when
    their question disappears. They remain independently retained event evidence.
    """
    assert_lock_context(locks)
    parent = resolve_subject(subject, lock=True)
    if not _draft(parent):
        return 0
    keep = {row["id"] for row in (snapshot or {}).get("answers", [])
            if row.get("type") == "age_at_event"}
    rows = EventAnswerDerivation.objects.filter(**subject_filter(subject)).exclude(question_id__in=keep)
    removed = list(rows.filter(locked_at=None, source_history=[]).values_list("question_id", flat=True))
    if not removed:
        return 0
    delete_draft_sources_locked(actor_id=subject.owner_member_id, subject=subject,
        locks=locks, question_ids=removed, audit_actor_id=audit_actor_id)
    if not EventAnswerDerivation.objects.filter(**subject_filter(subject)).exists() and parent.date_review_required:
        parent.date_review_required = False
        parent.save(update_fields=["date_review_required"])
    return len(removed)


def prune_definition_drafts_locked(*, event, key, target, previous, schema, actor, locks):
    """The form editor owns permission; F/P still own source eligibility/deletion."""
    if key not in ("application", "volunteer", "mentor"):
        return 0
    assert_lock_context(locks)
    old = previous.get("questions", []) if isinstance(previous, dict) else (previous or [])
    new = schema.get("questions", []) if isinstance(schema, dict) else (schema or [])
    removed = {q["id"] for q in old if q["type"] == "age_at_event"} - {
        q["id"] for q in new if q["type"] == "age_at_event"}
    if not removed:
        return 0
    kind = SubjectKind.APPLICATION if key == "application" else SubjectKind.ROLE_ASSIGNMENT
    parents = subject_model(kind).objects.filter(event=event, state="draft", answer_locked_at=None,
        member__is_active=True, member__access_status="active", member__retired_at=None,
        member__is_tenant_dump_stub=False)
    if kind == SubjectKind.ROLE_ASSIGNMENT:
        parents = parents.filter(posting_id=target.pk)
    total = 0
    for parent in parents.select_for_update().order_by("pk"):
        if not _draft(parent):
            continue
        subject = binding_for(parent, kind)
        # Keep every source except the removed authored age questions.
        keep = EventAnswerDerivation.objects.filter(**subject_filter(subject)).exclude(
            question_id__in=removed).values_list("question_id", flat=True)
        eligible = set(EventAnswerDerivation.objects.filter(**subject_filter(subject),
            question_id__in=removed, locked_at=None, source_history=[]).values_list("question_id", flat=True))
        deleted = prune_answer_sources_locked(subject=subject, locks=locks, audit_actor_id=actor.pk,
            snapshot={"answers": [{"id": qid, "type": "age_at_event"} for qid in keep]})
        if deleted:
            # Draft projection must not retain dangling references to deleted sources.
            field = "answers_snapshot" if kind == SubjectKind.APPLICATION else "answers"
            snapshot = json.loads(getattr(parent, field))
            snapshot["answers"] = [answer for answer in snapshot.get("answers", []) if answer["id"] not in eligible]
            setattr(parent, field, json.dumps(snapshot, separators=(",", ":")))
            parent.version += 1
            parent.save(update_fields=[field, "version"])
            total += deleted
    return total
