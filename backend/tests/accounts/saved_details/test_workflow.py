from uuid import uuid4

import pytest
from django.db import connection

from apps.accounts.models import User
from apps.accounts.saved_details.errors import SavedDetailsError
from apps.accounts.saved_details.models import MemberSavedDetail, SavedDetailCommandReceipt
from apps.accounts.saved_details.workflow import change_detail, list_details

pytestmark = pytest.mark.django_db(transaction=True)


def command(value="Maker College", version=0):
    return {"operation_id": uuid4(), "expected_version": version, "value": value, "save_consent": True}


def test_owner_without_membership_can_save_but_login_and_profile_are_unchanged(owner):
    before = (owner.first_name, owner.phone_e164, owner.email)
    result = change_detail(owner.pk, "institution", command())
    assert result["version"] == 1
    owner.refresh_from_db()
    assert before == (owner.first_name, owner.phone_e164, owner.email)
    assert list_details(owner.pk)["fields"][0]["value"] == "Maker College"
    with connection.cursor() as cursor:
        cursor.execute("SELECT value_envelope FROM accounts_membersaveddetail WHERE user_id=%s", [owner.pk])
        stored = cursor.fetchone()[0]
    assert stored.startswith("pii:account:gcm:v1:") and "Maker College" not in stored


def test_same_operation_replays_and_changed_body_conflicts(owner):
    body = command()
    first = change_detail(owner.pk, "institution", body)
    assert change_detail(owner.pk, "institution", body) == first
    with pytest.raises(SavedDetailsError) as error:
        change_detail(owner.pk, "institution", {**body, "value": "Other"})
    assert error.value.status_code == 409
    assert MemberSavedDetail.objects.get(user=owner).version == 1


def test_delete_retains_version_and_old_command_cannot_resurrect_value(owner):
    initial = command()
    change_detail(owner.pk, "institution", initial)
    deleted = change_detail(owner.pk, "institution", {"operation_id": uuid4(), "expected_version": 1}, delete=True)
    assert deleted["version"] == 2
    assert list_details(owner.pk)["fields"][0]["value"] is None
    assert list_details(owner.pk)["fields"][0]["version"] == 2
    assert change_detail(owner.pk, "institution", initial)["version"] == 1  # receipt replay only
    assert MemberSavedDetail.objects.get(user=owner).deleted_at is not None
    with pytest.raises(SavedDetailsError):
        change_detail(owner.pk, "institution", command("Old", 0))
    assert change_detail(owner.pk, "institution", command("New", 2))["version"] == 3


def test_replay_receipts_never_retain_copies_of_deleted_private_values(owner):
    body = command("2004-05-12")
    change_detail(owner.pk, "date_of_birth", body)
    receipt = SavedDetailCommandReceipt.objects.get(user=owner)
    assert receipt.response_metadata == {"field_key": "date_of_birth", "version": 1}
    assert "2004-05-12" not in str(receipt.response_metadata)


@pytest.mark.parametrize("field", ["date_of_birth", "dietary_needs", "accessibility_needs", "emergency_contact", "resume"])
def test_sensitive_save_is_explicit(owner, field):
    with pytest.raises(SavedDetailsError):
        change_detail(owner.pk, field, {**command(), "save_consent": False})
    assert not MemberSavedDetail.objects.filter(user=owner).exists()


def test_stub_accounts_cannot_read_even_their_own_vault(owner):
    # Model constraints protect persisted account contexts; mutate the loaded
    # boundary via a real retired/stub account instead of forging staff rows.
    User.objects.filter(pk=owner.pk).update(is_tenant_dump_stub=True)
    with pytest.raises(SavedDetailsError) as error:
        list_details(owner.pk)
    assert error.value.status_code == 403


def test_unknown_and_derived_keys_are_not_saved(owner):
    for key in ("age_at_event", "login_phone", "custom-label"):
        with pytest.raises(SavedDetailsError):
            change_detail(owner.pk, key, command())
    assert not MemberSavedDetail.objects.filter(user=owner).exists()
