"""Draft question removal minimizes private sources without deleting submitted evidence."""
import json
from uuid import uuid4

import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.events.contracts.subjects import SubjectKind
from apps.events.answer_derivations.models import EventAnswerDerivation
from apps.events.services_write_boundary import write_boundary
from apps.events.programme_locks import current_locks
from apps.events.programme.draft_sources import prune_answer_sources_locked, prune_definition_drafts_locked
from apps.events.programme.prepared_forms import prepare as prepare_form
from tests.events.programme.answer_derivations.conftest import age_world, create_subject, prepare, insert

pytestmark = pytest.mark.django_db(transaction=True)


def test_owner_draft_removal_deletes_only_omitted_unlocked_source(age_world):
    row, subject = create_subject(age_world, SubjectKind.APPLICATION)
    insert(age_world, subject, prepare(age_world, subject))
    with write_boundary(age_world[3], account_ids=[subject.owner_member_id]):
        assert prune_answer_sources_locked(subject=subject, snapshot={"answers": []},
            locks=current_locks(subject.event_id)) == 1
    assert not EventAnswerDerivation.objects.filter(application=row).exists()


def test_submitted_parent_retains_private_source_even_if_its_question_disappears(age_world):
    row, subject = create_subject(age_world, SubjectKind.APPLICATION)
    insert(age_world, subject, prepare(age_world, subject))
    row.submitted_at = timezone.now()
    row.save(update_fields=["submitted_at"])
    with write_boundary(age_world[3], account_ids=[subject.owner_member_id]):
        assert prune_answer_sources_locked(subject=subject, snapshot={"answers": []},
            locks=current_locks(subject.event_id)) == 0
    assert EventAnswerDerivation.objects.filter(application=row).exists()


def test_form_definition_cleanup_does_not_leave_dangling_draft_answer_reference(age_world):
    row, subject = create_subject(age_world, SubjectKind.APPLICATION)
    insert(age_world, subject, prepare(age_world, subject))
    source = EventAnswerDerivation.objects.get(application=row)
    row.answers_snapshot = json.dumps({"version": 2, "answers": [{"id": "age", "type": "age_at_event", "derivation_id": source.pk}]})
    row.save(update_fields=["answers_snapshot"])
    with write_boundary(age_world[3], account_ids=[subject.owner_member_id]):
        count = prune_definition_drafts_locked(event=age_world[3], key="application", target=None,
            previous={"questions": [{"id": "age", "type": "age_at_event"}]}, schema={"questions": []},
            actor=age_world[0], locks=current_locks(subject.event_id))
    row.refresh_from_db()
    assert count == 1 and json.loads(row.answers_snapshot)["answers"] == []
    assert not EventAnswerDerivation.objects.filter(pk=source.pk).exists()


def test_reconstructed_removed_ids_are_dropped_but_explicit_unknown_ids_still_refuse(age_world):
    row, subject = create_subject(age_world, SubjectKind.APPLICATION)
    schema = {"schema_version": 2, "form_id": "current", "revision": 2, "questions": []}
    payload = {"form": {"schema_version": 2, "form_id": "current", "revision": 2}, "answers": {}, "operation_id": str(uuid4())}
    previous = json.dumps({"version": 2, "answers": [{"id": "removed", "type": "text", "value": "old"},
        {"id": "old_age", "type": "age_at_event", "derivation_id": 123}]})
    result = prepare_form(actor_id=subject.owner_member_id, subject=subject, schema=schema,
        payload=payload, submit=False, previous_answers=previous)
    assert result.snapshot["answers"] == []
    with pytest.raises(ValidationError):
        prepare_form(actor_id=subject.owner_member_id, subject=subject, schema=schema,
            payload={**payload, "answers": {"removed": "client value"}}, submit=False, previous_answers=previous)
