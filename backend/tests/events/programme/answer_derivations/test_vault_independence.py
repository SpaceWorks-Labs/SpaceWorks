"""Vault deletion must not delete independently submitted tenant DOB evidence."""

from uuid import uuid4

import pytest
from cryptography.fernet import Fernet

from apps.accounts.saved_details import fields
from apps.accounts.saved_details.age import validate_dob
from apps.accounts.saved_details.workflow import change_detail, saved_dob_loader
from apps.events.answer_derivations.preparation import prepare_derivations
from apps.events.answer_derivations.serialization import owner_export
from apps.events.contracts.subjects import SubjectKind

from .conftest import create_subject, insert

pytestmark = pytest.mark.django_db(transaction=True)


class DobRegistry:
    """Isolate account transport; F owns the full mapped form vocabulary."""

    def descriptors(self):
        return ({"field_key": "date_of_birth", "type": "date_of_birth", "sensitive": True,
                 "persistable": True, "default_save": False},)

    def normalize(self, key, value):
        assert key == "date_of_birth"
        return validate_dob(value).isoformat()


def saved_preparation(age_world, settings, monkeypatch, role):
    settings.ACCOUNT_SAVED_DETAILS_ENABLED = True
    settings.ACCOUNT_PII_KEY_BROKER = "local"
    settings.ACCOUNT_PII_MASTER_KEY = Fernet.generate_key().decode()
    monkeypatch.setattr(fields, "_provider", DobRegistry())
    owner = age_world[0]
    _, subject = create_subject(age_world, SubjectKind.ROLE_ASSIGNMENT, role=role)
    saved = change_detail(owner.pk, "date_of_birth", {
        "operation_id": uuid4(), "expected_version": 0, "value": "2004-05-12", "save_consent": True,
    })
    prepared = prepare_derivations(
        actor_id=owner.pk, subject=subject, derivations={"age": {
            "source": {"kind": "saved_detail", "field_key": "date_of_birth", "version": saved["version"]},
            "reviewed_event_date_revision": 7, "reviewed_as_of_date": "2026-12-01",
        }}, visible_question_ids=("age",), form_sha256="a" * 64, canonical_answer_sha256="b" * 64,
        saved_dob_loader=saved_dob_loader,
    )
    return owner, subject, saved, prepared


@pytest.mark.parametrize("role", ["volunteer", "mentor"])
def test_delete_saved_dob_retains_role_only_event_evidence(age_world, settings, monkeypatch, role):
    owner, subject, saved, prepared = saved_preparation(age_world, settings, monkeypatch, role)
    insert(age_world, subject, prepared)
    change_detail(owner.pk, "date_of_birth", {
        "operation_id": uuid4(), "expected_version": saved["version"],
    }, delete=True)
    assert owner_export(actor_id=owner.pk, subject=subject)[0]["source_date_of_birth"] == "2004-05-12"
    from apps.accounts.saved_details.errors import SavedDetailsError
    with pytest.raises(SavedDetailsError):
        saved_dob_loader(actor_id=owner.pk, version=saved["version"])


def test_saved_dob_prepared_before_account_erase_cannot_be_inserted(age_world, settings, monkeypatch):
    from apps.accounts.saved_details.lifecycle import erase_account_vault
    from apps.events.answer_derivations.models import EventAnswerDerivation

    owner, subject, _, prepared = saved_preparation(age_world, settings, monkeypatch, "mentor")
    # No save intent/true save choice is involved. The already-encrypted tenant
    # source must still obey the account erasure fence at event insertion.
    erase_account_vault(owner.pk, actor=owner)
    # Plan §10A: an erased account epoch refuses with 409 account_key_changed.
    from apps.events.answer_derivations.errors import DerivationError
    with pytest.raises(DerivationError) as refused:
        insert(age_world, subject, prepared)
    assert refused.value.detail["code"] == "account_key_changed"
    assert not EventAnswerDerivation.objects.filter(event_id=subject.event_id).exists()
