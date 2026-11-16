"""P-add-on contract fixtures; G supplies the real stage resolver/type at integration."""
from dataclasses import dataclass, replace
from datetime import date
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet

from apps.accounts.models import User
from apps.accounts.saved_details import fields, intents, prefill
from apps.accounts.saved_details.errors import SavedDetailsError
from apps.accounts.saved_details.models import MemberSavedDetail, SavedDetailUpdateIntent
from apps.accounts.saved_details.serializers import SavedVaultPrefillInput
from apps.accounts.saved_details.subject_binding import require_subject
from apps.accounts.saved_details.workflow import change_detail
from apps.forms_schema.profile_fields import PROFILE_FIELDS, normalize_profile_value

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def owner(settings, monkeypatch):
    settings.ACCOUNT_SAVED_DETAILS_ENABLED = True
    settings.ACCOUNT_PII_KEY_BROKER = "local"
    settings.ACCOUNT_PII_MASTER_KEY = Fernet.generate_key().decode()
    settings.ACCOUNT_PII_MASTER_KEY_PREVIOUS = ""
    settings.PII_ENCRYPTION_ENABLED = False
    adapter = SimpleNamespace(
        descriptors=lambda: tuple({"field_key": item.field_key, "persistable": item.persistable,
            "sensitive": item.sensitive, "default_save": item.default_save} for item in PROFILE_FIELDS.values()),
        normalize=normalize_profile_value,
    )
    monkeypatch.setattr(fields, "_provider", adapter)
    return User.objects.create_user(username=f"stage-vault-{uuid4().hex}")


@dataclass(frozen=True, kw_only=True)
class StageSubject:
    """Executable model-free shape for G's separate StageResponseSubject.

    Deliberately NOT a new member of SubjectKind or a DOB AnswerSubject.
    """
    event_id: int
    owner_member_id: int
    kind: str = "stage_response"
    subject_id: int | None = None
    creation_operation_id: UUID | None = None


QUESTIONS = (
    {"id": "school", "type": "short_text", "profile_field_key": "institution"},
    {"id": "food", "type": "long_text", "profile_field_key": "dietary_needs", "sensitive": True},
    {"id": "birth", "type": "date_of_birth", "profile_field_key": "date_of_birth"},
    {"id": "age", "type": "age_at_event", "profile_field_key": "age_at_event"},
    {"id": "bypass", "type": "age_at_event", "profile_field_key": "institution"},
)


def context_for(owner, monkeypatch, *, subject=None, stage_form_id=8, questions=QUESTIONS):
    subject = subject or StageSubject(event_id=42, owner_member_id=owner.pk, subject_id=81)
    context = prefill.PrefillContext(owner_id=owner.pk, event_id=42, subject_kind="stage_response",
        form_id="arrival", form_revision=3, event_date_revision=7, as_of_date=date(2026, 12, 1),
        questions=questions, subject=subject, stage_form_id=stage_form_id)
    monkeypatch.setattr(prefill, "_provider", SimpleNamespace(resolve=lambda **_: context))
    selector = {"event_id": 42, "makerspace_id": 9, "subject_kind": "stage_response", "stage_form_id": stage_form_id}
    selector.update({"subject_id": subject.subject_id} if subject.subject_id else {"creation_operation_id": subject.creation_operation_id})
    return {"context": selector, "form_id": "arrival", "form_revision": 3, "event_date_revision": 7}, context


def save(owner, key, value, version=0):
    return change_detail(owner.pk, key, {"operation_id": uuid4(), "expected_version": version, "value": value, "save_consent": True})


def test_stage_prefill_excludes_dob_and_derivations_without_reading_source(owner, monkeypatch):
    save(owner, "institution", "Maker College")
    save(owner, "dietary_needs", "Vegetarian")
    save(owner, "date_of_birth", "2004-05-12")
    body, _ = context_for(owner, monkeypatch)
    original = prefill.open_value
    opened = []

    def checked(row, field):
        opened.append(row.field_key)
        assert row.field_key != "date_of_birth"
        return original(row, field)

    monkeypatch.setattr(prefill, "open_value", checked)
    result = prefill.prefill(owner.pk, body)
    assert result["values"] == {"institution": "Maker College", "dietary_needs": "Vegetarian"}
    assert result["saved_detail_versions"] == {"institution": 1, "dietary_needs": 1}
    assert result["save_defaults"] == {"institution": True, "dietary_needs": False}
    assert result["derivation_inputs"] == {} and "2004-05-12" not in str(result)
    assert opened == ["institution", "dietary_needs"]
    assert not SavedDetailUpdateIntent.objects.exists()


def test_stage_prefill_honors_owner_edits_and_tombstones_across_forms(owner, monkeypatch):
    save(owner, "institution", "First College")
    body, _ = context_for(owner, monkeypatch)
    assert prefill.prefill(owner.pk, body)["values"]["institution"] == "First College"
    save(owner, "institution", "Second College", 1)
    next_body, _ = context_for(owner, monkeypatch, stage_form_id=9,
        subject=StageSubject(event_id=42, owner_member_id=owner.pk, subject_id=82))
    assert prefill.prefill(owner.pk, next_body)["values"]["institution"] == "Second College"
    change_detail(owner.pk, "institution", {"operation_id": uuid4(), "expected_version": 2}, delete=True)
    result = prefill.prefill(owner.pk, next_body)
    assert "institution" not in result["values"] and result["saved_detail_versions"]["institution"] == 3
    assert MemberSavedDetail.objects.get(user=owner, field_key="institution").deleted_at is not None


def test_sensitive_question_for_standard_field_cannot_default_save_on(owner, monkeypatch):
    body, _ = context_for(owner, monkeypatch, questions=(QUESTIONS[0], {**QUESTIONS[0], "id": "sensitive-school", "sensitive": True}))
    assert prefill.prefill(owner.pk, body)["save_defaults"]["institution"] is False


def test_virtual_stage_prefill_uses_exact_owner_creation_binding(owner, monkeypatch):
    subject = StageSubject(event_id=42, owner_member_id=owner.pk, creation_operation_id=uuid4())
    body, _ = context_for(owner, monkeypatch, subject=subject)
    serializer = SavedVaultPrefillInput(data=body)
    assert serializer.is_valid(), serializer.errors
    assert prefill.prefill(owner.pk, serializer.validated_data)["derivation_inputs"] == {}
    wrong = {**body, "context": {**body["context"], "creation_operation_id": uuid4()}}
    with pytest.raises(SavedDetailsError) as error:
        prefill.prefill(owner.pk, wrong)
    assert error.value.status_code == 404
    assert not MemberSavedDetail.objects.exists() and not SavedDetailUpdateIntent.objects.exists()


@pytest.mark.parametrize("change", [{"subject_id": 99}, {"stage_form_id": 99}, {"event_id": 99}, {"subject_kind": "application"}])
def test_foreign_stage_selector_never_reads_values(owner, monkeypatch, change):
    body, _ = context_for(owner, monkeypatch)
    monkeypatch.setattr(prefill, "open_value", lambda *_: pytest.fail("foreign prefill decrypted a value"))
    with pytest.raises(SavedDetailsError) as error:
        prefill.prefill(owner.pk, {**body, "context": {**body["context"], **change}})
    assert error.value.status_code == 404


@pytest.mark.parametrize("change", [{"owner_member_id": 999999}, {"event_id": 99}, {"kind": "finance_payee"}])
def test_foreign_typed_stage_binding_is_rejected(owner, monkeypatch, change):
    body, context = context_for(owner, monkeypatch)
    bad = replace(context, subject=replace(context.subject, **change))
    monkeypatch.setattr(prefill, "_provider", SimpleNamespace(resolve=lambda **_: bad))
    with pytest.raises(SavedDetailsError):
        prefill.prefill(owner.pk, body)


@pytest.mark.parametrize("selector", [
    {"subject_id": 81, "creation_operation_id": str(uuid4()), "stage_form_id": 8},
    {"stage_form_id": 8}, {"creation_operation_id": str(uuid4())},
    {"subject_id": 0}, {"subject_id": 81, "posting_id": 1},
])
def test_stage_selector_requires_exactly_one_binding(owner, selector):
    serializer = SavedVaultPrefillInput(data={"context": {"event_id": 42, "makerspace_id": 9, "subject_kind": "stage_response", **selector},
        "form_id": "arrival", "form_revision": 3, "event_date_revision": 7})
    assert not serializer.is_valid()


def test_stale_stage_date_and_form_return_typed_reload_errors(owner, monkeypatch):
    body, _ = context_for(owner, monkeypatch)
    for changed, expected in (({"event_date_revision": 8}, "event_date_changed"), ({"form_revision": 4}, "form_revision_changed")):
        with pytest.raises(SavedDetailsError) as error:
            prefill.prefill(owner.pk, {**body, **changed})
        assert error.value.status_code == 409 and error.value.detail["code"] == expected
        assert "age" not in str(error.value.detail["detail"])


@pytest.mark.parametrize("key", ["date_of_birth", "age_at_event"])
def test_stage_save_rejects_age_mapping_even_when_unselected(owner, key):
    subject = StageSubject(event_id=42, owner_member_id=owner.pk, subject_id=81)
    form = intents.ValidatedSaveInput(subject=subject, mapped_values={key: "2004-05-12"}, canonical_answers={}, form_descriptor={}, event_date_revision=7)
    with pytest.raises(SavedDetailsError) as error:
        intents.prepare_saved_detail_intent(actor_id=owner.pk, subject=subject, validated_form=form, choices={key: False}, base_versions={}, operation_id=uuid4())
    assert error.value.detail["code"] == "stage_age_question_unsupported"


@pytest.mark.parametrize("key", ["bank_account", "ifsc", "upi", "paypal", "payee"])
def test_payee_keys_and_subject_are_not_saved_details(owner, key):
    with pytest.raises(SavedDetailsError):
        fields.descriptor(key)
    with pytest.raises(SavedDetailsError):
        require_subject(StageSubject(event_id=42, owner_member_id=owner.pk, kind="finance_payee", subject_id=81))
