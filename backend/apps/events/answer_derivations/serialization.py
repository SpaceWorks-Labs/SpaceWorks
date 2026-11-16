"""Response/report projections; only the owner's export can expose source DOB."""

from rest_framework.exceptions import NotFound

from apps.accounts import rbac
from apps.accounts.saved_details.age import age_on
from apps.events import event_authority
from apps.events.event_permissions import MANAGE_REGISTRATIONS

from .crypto import decrypt_source
from .dates import event_date, review_target
from .models import EventAnswerDerivation
from .subjects import require_member, require_owner, resolve_subject, subject_filter


def _source(subject, question_id):
    # Resolve the typed parent independently of client-supplied derivation IDs.
    source = resolve_subject(subject)
    row = EventAnswerDerivation.objects.filter(
        **subject_filter(subject), question_id=question_id,
    ).first()
    if row is None:
        raise NotFound()
    return source, row


def _project(row):
    as_of = row.as_of_date if row.locked_at else event_date(row.event)
    return {
        "id": row.question_id, "type": "age_at_event",
        "value": age_on(decrypt_source(row), as_of), "as_of_date": as_of.isoformat(),
        "locked": row.locked_at is not None,
    }


def project_owner(*, actor_id, subject, question_id):
    require_owner(actor_id, subject)
    _, row = _source(subject, question_id)
    return _project(row)


def project_organizer(*, actor_id, subject, question_id, disclosure_policy):
    """Trusted schema/review adapter supplies the live disclosure policy.

    It must explicitly allow this question after applying blind-review rules.
    A missing/false policy omits age before touching any encrypted source.
    Staff authority alone cannot reveal a source DOB, including in CSV/templates.
    """
    from apps.accounts.models import User

    actor = User.objects.get(pk=actor_id)
    source = resolve_subject(subject)
    event = source.event
    event_authority.require(actor, event, MANAGE_REGISTRATIONS)
    if not rbac.can(actor, rbac.Action.VIEW_AUDIT, event.makerspace_id):
        from rest_framework.exceptions import PermissionDenied
        raise PermissionDenied()
    if (disclosure_policy is None or disclosure_policy(
        actor_id=actor_id, subject=subject, question_id=question_id,
    ) is not True):
        return None
    _, row = _source(subject, question_id)
    return _project(row)


def answer_review(*, actor_id, subject):
    require_owner(actor_id, subject)
    source = resolve_subject(subject)
    rows = list(EventAnswerDerivation.objects.filter(**subject_filter(subject)))
    revision, as_of = review_target(source.event, rows)
    return {
        "event_date_revision": revision, "as_of_date": as_of.isoformat(),
        "locked": bool(rows) and all(row.locked_at for row in rows),
        "date_review_required": bool(source.date_review_required),
    }


def owner_export(*, actor_id, subject):
    """Separate from the global vault archive; sources belong to their event."""
    require_owner(actor_id, subject)
    result = []
    for row in EventAnswerDerivation.objects.filter(**subject_filter(subject)).order_by("question_id"):
        source = {
            "event_id": subject.event_id, "subject_kind": subject.kind.value,
            "subject_id": subject.subject_id, "question_id": row.question_id,
            "source_date_of_birth": decrypt_source(row), "version": row.version,
            "event_date_revision": row.event_date_revision,
            "as_of_date": (row.as_of_date if row.locked_at else event_date(row.event)).isoformat(),
            "locked": row.locked_at is not None,
            "source_history": [],
        }
        for snapshot in row.source_history:
            source["source_history"].append({
                "source_date_of_birth": decrypt_source(row, envelope=snapshot["source_dob_envelope"]),
                "version": snapshot["version"], "as_of_date": snapshot["as_of_date"],
                "event_date_revision": snapshot["event_date_revision"], "locked_at": snapshot["locked_at"],
            })
        result.append(source)
    return result


def personal_data_export(*, actor_id):
    """Owner-only adapter G composes explicitly into the personal-data archive."""
    from apps.events.contracts.subjects import SubjectKind
    from .subjects import binding_for, subject_model

    require_member(actor_id)
    records = []
    for kind in SubjectKind:
        rows = subject_model(kind).objects.filter(member_id=actor_id)
        for source in rows.iterator(chunk_size=200):
            if EventAnswerDerivation.objects.filter(**subject_filter(binding_for(source, kind))).exists():
                records.extend(owner_export(actor_id=actor_id, subject=binding_for(source, kind)))
    return records


class OwnerAgeProvider:
    """Request-bound implementation of contracts.providers.AgeProvider."""

    def __init__(self, actor_id):
        self.actor_id = actor_id

    def project(self, *, subject, question_id):
        return project_owner(actor_id=self.actor_id, subject=subject, question_id=question_id)

    def review_date_locked(self, *, subject, revision, as_of_date, locks):
        from .lifecycle import review_date_locked
        return review_date_locked(
            actor_id=self.actor_id, subject=subject, revision=revision,
            as_of_date=as_of_date, locks=locks,
        )
