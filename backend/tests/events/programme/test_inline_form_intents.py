"""Real account DB/fence tests, with an executable G pending-slot-map adapter.

G/R must additionally run canonical registration/application rollback/replay tests
after integrating their stage rows and outer EventCommandReceipt bridge.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4, uuid5

import pytest
from django.db import close_old_connections, transaction
from django.utils import timezone

from apps.accounts.saved_details import commands, intents, subject_binding
from apps.accounts.saved_details.errors import SavedDetailsError
from apps.accounts.saved_details.lifecycle import erase_account_vault, expire_intents_and_receipts
from apps.accounts.saved_details.models import MemberSavedDetail, SavedDetailUpdateIntent
from apps.accounts.saved_details.workflow import change_detail
from apps.encryption.account_models import AccountPiiKey
from apps.encryption.account_write_fence import AccountKeyChanged, account_fences
from apps.events.contracts.providers import LockedContext
from apps.events.contracts.subjects import AnswerSubject, SubjectKind
from apps.tenant_migration.gate_locks import shared_boundary
from tests.events.programme.test_stage_saved_details import StageSubject, owner  # noqa: F401

pytestmark = pytest.mark.django_db(transaction=True)


def child(outer, owner_id, slot):
    # Frozen G contract oracle. Production identity generation remains G-owned.
    return uuid5(outer, f"events-form:v1:42:{owner_id}:{slot}")


def make_forms(owner, outer, order=(8, 9), *, values=None, versions=None):
    forms = {}
    for slot in ("base", *(f"stage:{pk}" for pk in order)):
        operation = child(outer, owner.pk, slot)
        subject = (AnswerSubject(event_id=42, owner_member_id=owner.pk, kind=SubjectKind.REGISTRATION, creation_operation_id=operation)
                   if slot == "base" else StageSubject(event_id=42, owner_member_id=owner.pk, creation_operation_id=operation))
        form = intents.ValidatedSaveInput(subject=subject, mapped_values={"institution": (values or {}).get(slot, " Maker College ")},
            canonical_answers={"school": "Maker College"}, form_descriptor={"form_id": slot, "revision": 3}, event_date_revision=7)
        forms[slot] = (form, {"institution": True}, {"institution": (versions or {}).get(slot, 0)})
    return forms


def prepare_forms(owner, outer, forms):
    intents.validate_form_save_conflicts(forms)
    return {slot: intents.prepare_saved_detail_intent(actor_id=owner.pk, subject=form.subject, validated_form=form,
        choices=choices, base_versions=versions, operation_id=child(outer, owner.pk, slot), outer_operation_id=outer, form_slot=slot)
        for slot, (form, choices, versions) in forms.items()}


def install_binding(monkeypatch, outer, forms, preparations):
    bound = {slot: replace(form.subject, subject_id=100 + index, creation_operation_id=None)
             for index, (slot, (form, _, _)) in enumerate(sorted(forms.items()))}
    pending = {preparations[slot].operation_id: slot for slot in bound}

    def verify(*, prepared_subject, actual_subject, operation_id, locks):
        slot = pending[operation_id]
        form, choices, _ = forms[slot]
        assert operation_id == child(outer, actual_subject.owner_member_id, slot)
        assert prepared_subject.creation_operation_id == operation_id
        assert actual_subject == bound[slot] and locks.event_id == actual_subject.event_id
        return subject_binding.VerifiedIntentBinding(
            form_sha256=intents.digest(form.form_descriptor), canonical_answer_sha256=intents.digest(form.canonical_answers),
            event_date_revision=form.event_date_revision, chosen_fields=tuple(k for k, save in choices.items() if save),
            form_operation=subject_binding.VerifiedFormOperation(outer_operation_id=outer, slot=slot, operation_id=operation_id,
                event_id=42, owner_member_id=actual_subject.owner_member_id, subject_kind=str(actual_subject.kind), subject_id=actual_subject.subject_id))

    monkeypatch.setattr(subject_binding, "_provider", SimpleNamespace(require_binding=verify))
    return bound


def insert_all(owner, preparations, bound):
    ids = {}
    with shared_boundary(0), transaction.atomic(), account_fences([owner.pk]):
        for slot in sorted(preparations):
            ids[slot] = intents.insert_prepared_locked(preparations[slot], subject=bound[slot],
                locks=LockedContext(event_id=42, tenant_ids=(), account_ids=(owner.pk,)))
    return ids


def test_base_plus_two_stages_have_distinct_order_independent_child_operations(owner, monkeypatch):
    outer = uuid4()
    forms = make_forms(owner, outer)
    prepared = prepare_forms(owner, outer, forms)
    reversed_forms = make_forms(owner, outer, order=(9, 8))
    reversed_prepared = prepare_forms(owner, outer, reversed_forms)
    assert len({item.operation_id for item in prepared.values()}) == 3
    assert {slot: item.operation_id for slot, item in prepared.items()} == {slot: item.operation_id for slot, item in reversed_prepared.items()}
    bound = install_binding(monkeypatch, outer, forms, prepared)
    ids = insert_all(owner, prepared, bound)
    assert SavedDetailUpdateIntent.objects.count() == 3
    assert set(SavedDetailUpdateIntent.objects.values_list("subject_kind", flat=True)) == {"registration", "stage_response"}
    for slot in sorted(ids):
        intents.apply_intent(ids[slot])
    statuses = [intents.intent_status(owner.pk, prepared[slot].operation_id) for slot in sorted(ids)]
    assert [status["fields"]["institution"]["state"] for status in statuses] == ["applied", "unchanged", "unchanged"]
    assert all(status["state"] == "applied" for status in statuses)
    assert MemberSavedDetail.objects.get(user=owner, field_key="institution").version == 1
    assert not SavedDetailUpdateIntent.objects.exclude(encrypted_payload="").exists()


@pytest.mark.parametrize("kwargs", [{"values": {"stage:9": "Different College"}}, {"versions": {"stage:9": 1}}])
def test_conflicting_common_values_or_versions_fail_before_key_or_intent_creation(owner, kwargs):
    forms = make_forms(owner, uuid4(), **kwargs)
    with pytest.raises(SavedDetailsError) as error:
        intents.validate_form_save_conflicts(forms)
    assert error.value.status_code == 409 and error.value.detail["code"] == "saved_detail_form_conflict"
    assert error.value.detail["field_keys"] == ["institution"]
    assert "Different College" not in str(error.value.detail)
    assert not AccountPiiKey.objects.filter(user=owner).exists()
    assert not SavedDetailUpdateIntent.objects.exists()


def test_unselected_conflicting_values_need_no_intent(owner):
    outer = uuid4()
    forms = make_forms(owner, outer, values={"stage:9": "Different College"})
    form, _, _ = forms["stage:9"]
    forms["stage:9"] = (form, {"institution": False}, {})
    prepared = prepare_forms(owner, outer, forms)
    assert prepared["stage:9"] is None


def test_final_form_binding_failure_rolls_back_every_account_intent_and_audit(owner, monkeypatch):
    from apps.audit.models import AuditLog
    outer = uuid4()
    forms = make_forms(owner, outer)
    prepared = prepare_forms(owner, outer, forms)
    bound = install_binding(monkeypatch, outer, forms, prepared)
    before = AuditLog.objects.count()
    prepared["stage:9"] = replace(prepared["stage:9"], canonical_answer_sha256="f" * 64)
    with pytest.raises(SavedDetailsError) as error:
        insert_all(owner, prepared, bound)
    assert error.value.detail["code"] == "answers_changed"
    assert not SavedDetailUpdateIntent.objects.exists() and not MemberSavedDetail.objects.exists()
    assert AuditLog.objects.count() == before


@pytest.mark.parametrize("change", ["outer", "slot", "missing", "subject"])
def test_inline_binding_rejects_wrong_pending_slot_proof(owner, monkeypatch, change):
    outer = uuid4()
    forms = make_forms(owner, outer)
    prepared = prepare_forms(owner, outer, forms)
    bound = install_binding(monkeypatch, outer, forms, prepared)
    real = subject_binding._provider.require_binding

    def changed(**kwargs):
        result = real(**kwargs)
        proof = result.form_operation
        proof = None if change == "missing" else replace(proof, **({"outer_operation_id": uuid4()} if change == "outer" else
            {"slot": "stage:999"} if change == "slot" else {"subject_id": 999}))
        return replace(result, form_operation=proof)

    monkeypatch.setattr(subject_binding, "_provider", SimpleNamespace(require_binding=changed))
    with pytest.raises(SavedDetailsError) as error:
        insert_all(owner, prepared, bound)
    assert error.value.detail["code"] == "invalid_subject" and not SavedDetailUpdateIntent.objects.exists()


def test_virtual_preparation_still_requires_creation_uuid_equals_child(owner, monkeypatch):
    outer = uuid4()
    forms = make_forms(owner, outer)
    prepared = prepare_forms(owner, outer, forms)
    bound = install_binding(monkeypatch, outer, forms, prepared)
    prepared["base"] = replace(prepared["base"], subject=replace(forms["base"][0].subject, creation_operation_id=outer))
    with pytest.raises(SavedDetailsError):
        insert_all(owner, prepared, bound)
    assert not SavedDetailUpdateIntent.objects.exists()


def test_safe_form_statuses_include_not_requested_and_are_owner_scoped(owner, monkeypatch):
    outer = uuid4()
    forms = make_forms(owner, outer)
    prepared = prepare_forms(owner, outer, forms)
    bound = install_binding(monkeypatch, outer, forms, prepared)
    insert_all(owner, prepared, bound)
    slot_map = {slot: {"operation_id": str(prepared[slot].operation_id), "kind": str(subject.kind), "subject_id": subject.subject_id}
                for slot, subject in bound.items()}
    slot_map["stage:10"] = {"operation_id": str(child(outer, owner.pk, "stage:10")), "kind": "stage_response", "subject_id": 110}
    result = commands.form_intent_statuses(owner.pk, slot_map)
    assert commands.form_intent_statuses(owner.pk, dict(reversed(list(slot_map.items())))) == result
    assert result[1]["state"] == "not_requested"  # canonical lexicographic ordering, stage:10 before stage:8
    assert result[1]["intent_id"] is None and result[1]["status_url"] is None
    assert "Maker College" not in str(result) and "encrypted_payload" not in str(result)
    from apps.accounts.models import User
    foreign = User.objects.create_user(username=f"foreign-{uuid4().hex}")
    with pytest.raises(SavedDetailsError) as error:
        intents.intent_status(foreign.pk, prepared["base"].operation_id)
    assert error.value.status_code == 404


def test_stale_different_save_and_delete_win_over_each_form(owner, monkeypatch):
    outer = uuid4()
    forms = make_forms(owner, outer)
    prepared = prepare_forms(owner, outer, forms)
    bound = install_binding(monkeypatch, outer, forms, prepared)
    ids = insert_all(owner, prepared, bound)
    change_detail(owner.pk, "institution", {"operation_id": uuid4(), "expected_version": 0, "value": "Newer College", "save_consent": True})
    change_detail(owner.pk, "institution", {"operation_id": uuid4(), "expected_version": 1}, delete=True)
    for pk in ids.values():
        intents.apply_intent(pk)
    assert set(SavedDetailUpdateIntent.objects.values_list("state", flat=True)) == {"conflict"}
    row = MemberSavedDetail.objects.get(user=owner, field_key="institution")
    assert row.version == 2 and row.deleted_at is not None


def test_erasure_after_preparation_refuses_all_child_insertions(owner, monkeypatch):
    outer = uuid4()
    forms = make_forms(owner, outer)
    prepared = prepare_forms(owner, outer, forms)
    bound = install_binding(monkeypatch, outer, forms, prepared)
    erase_account_vault(owner.pk, actor=owner)
    with pytest.raises(AccountKeyChanged):
        insert_all(owner, prepared, bound)
    assert not SavedDetailUpdateIntent.objects.exists() and not MemberSavedDetail.objects.exists()


def test_expired_children_report_each_field_and_erase_ciphertext(owner, monkeypatch):
    outer = uuid4()
    forms = make_forms(owner, outer)
    prepared = prepare_forms(owner, outer, forms)
    bound = install_binding(monkeypatch, outer, forms, prepared)
    ids = insert_all(owner, prepared, bound)
    SavedDetailUpdateIntent.objects.filter(pk__in=ids.values()).update(expires_at=timezone.now() - timedelta(seconds=1))
    expire_intents_and_receipts()
    for preparation in prepared.values():
        status = intents.intent_status(owner.pk, preparation.operation_id)
        assert status["fields"]["institution"] == {"state": "failed", "code": "save_intent_expired"}
    assert not SavedDetailUpdateIntent.objects.exclude(encrypted_payload="").exists()


def test_concurrent_equal_child_saves_apply_once(owner, monkeypatch):
    outer = uuid4()
    forms = make_forms(owner, outer)
    prepared = prepare_forms(owner, outer, forms)
    bound = install_binding(monkeypatch, outer, forms, prepared)
    ids = insert_all(owner, prepared, bound)

    def apply(pk):
        close_old_connections()
        try:
            intents.apply_intent(pk)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=3) as pool:
        for future in [pool.submit(apply, pk) for pk in ids.values()]:
            future.result(timeout=20)
    assert MemberSavedDetail.objects.get(user=owner, field_key="institution").version == 1
    assert list(SavedDetailUpdateIntent.objects.values_list("state", flat=True)) == ["applied"] * 3
