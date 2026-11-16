from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.db import transaction

from apps.accounts.saved_details import intents, subject_binding
from apps.accounts.saved_details.errors import SavedDetailsError
from apps.accounts.saved_details.models import MemberSavedDetail, SavedDetailUpdateIntent
from apps.accounts.saved_details.workflow import change_detail, list_details
from apps.encryption.account_services import rotate_account_key
from apps.encryption.account_write_fence import account_fences
from apps.events.contracts.providers import LockedContext
from apps.events.contracts.subjects import AnswerSubject, SubjectKind
from apps.tenant_migration.gate_locks import shared_boundary

pytestmark = pytest.mark.django_db(transaction=True)


def prepared(owner, values=None, choices=None, versions=None):
    op = uuid4()
    subject = AnswerSubject(event_id=42, owner_member_id=owner.pk, kind=SubjectKind.ROLE_ASSIGNMENT, subject_id=81)
    form = intents.ValidatedSaveInput(subject=subject, mapped_values=values or {"institution": "Maker College"},
        canonical_answers={"answers": []}, form_descriptor={"revision": 3}, event_date_revision=7)
    result = intents.prepare_saved_detail_intent(actor_id=owner.pk, subject=subject, validated_form=form,
        choices={"institution": True} if choices is None else choices, base_versions=versions or {"institution": 0}, operation_id=op)
    return subject, form, result


def insert(owner, subject, form, result, monkeypatch, *, rollback=False):
    monkeypatch.setattr(subject_binding, "_provider", SimpleNamespace(require_binding=lambda **_: subject_binding.VerifiedIntentBinding(
        form_sha256=intents.digest(form.form_descriptor), canonical_answer_sha256=intents.digest(form.canonical_answers),
        event_date_revision=form.event_date_revision, chosen_fields=result.chosen_fields)))
    with shared_boundary(0), transaction.atomic(), account_fences([owner.pk]):
        pk = intents.insert_prepared_locked(result, subject=subject,
            locks=LockedContext(event_id=42, tenant_ids=(), account_ids=(owner.pk,)))
        if rollback:
            transaction.set_rollback(True)
    return pk


def test_no_true_choice_needs_no_key_even_when_disabled(owner, settings):
    settings.ACCOUNT_SAVED_DETAILS_ENABLED = False
    assert prepared(owner, choices={})[2] is None
    assert prepared(owner, choices={"institution": False})[2] is None


def test_rollback_has_no_intent_and_no_saved_detail(owner, monkeypatch):
    subject, form, result = prepared(owner)
    insert(owner, subject, form, result, monkeypatch, rollback=True)
    assert not SavedDetailUpdateIntent.objects.exists()
    assert not MemberSavedDetail.objects.exists()


def test_intent_applies_only_chosen_visible_values_and_retry_is_safe(owner, monkeypatch):
    subject, form, result = prepared(owner)
    pk = insert(owner, subject, form, result, monkeypatch)
    intents.apply_intent(pk)
    intents.apply_intent(pk)
    assert list_details(owner.pk)["fields"][0]["value"] == "Maker College"
    row = SavedDetailUpdateIntent.objects.get(pk=pk)
    assert row.state == "applied" and row.encrypted_payload == ""
    assert MemberSavedDetail.objects.get(user=owner).version == 1


def test_newer_save_or_delete_wins_over_old_intent(owner, monkeypatch):
    subject, form, result = prepared(owner)
    pk = insert(owner, subject, form, result, monkeypatch)
    change_detail(owner.pk, "institution", {"operation_id": uuid4(), "expected_version": 0, "value": "Newer", "save_consent": True})
    change_detail(owner.pk, "institution", {"operation_id": uuid4(), "expected_version": 1}, delete=True)
    intents.apply_intent(pk)
    status = intents.intent_status(owner.pk, result.operation_id)
    assert status["state"] == "conflict"
    assert status["fields"]["institution"] == {"state": "conflict", "current_version": 2}
    assert MemberSavedDetail.objects.get(user=owner).deleted_at is not None


def test_key_rotation_fails_old_intent_with_safe_review_status(owner, monkeypatch):
    subject, form, result = prepared(owner)
    pk = insert(owner, subject, form, result, monkeypatch)
    rotate_account_key(owner.pk, owner)
    intents.apply_intent(pk)
    status = intents.intent_status(owner.pk, result.operation_id)
    assert status["state"] == "failed" and status["code"] == "account_key_changed"
    assert not status["retryable"] and not MemberSavedDetail.objects.exists()


def test_expired_preparation_and_changed_schema_reject_before_insert(owner, monkeypatch):
    from dataclasses import replace
    from datetime import timedelta
    from django.utils import timezone
    subject, form, result = prepared(owner)
    with pytest.raises(SavedDetailsError):
        insert(owner, subject, form, replace(result, expires_at=timezone.now() - timedelta(seconds=1)), monkeypatch)
    with pytest.raises(SavedDetailsError):
        insert(owner, subject, replace(form, form_descriptor={"revision": 4}), result, monkeypatch)
    assert not SavedDetailUpdateIntent.objects.exists()
