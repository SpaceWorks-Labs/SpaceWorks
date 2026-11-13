"""Account erasure leaves independent submitted tenant evidence intact."""
import pytest
from django.db import connection
from django.utils import timezone

from apps.accounts.saved_details.lifecycle import erase_account_vault
from apps.encryption.account_models import PiiAccountWriteFence
from apps.encryption.account_write_fence import AccountKeyChanged, account_write
from apps.events.answer_derivations.models import EventAnswerDerivation
from apps.events.contracts.subjects import SubjectKind
from tests.events.programme.answer_derivations.conftest import age_world, create_subject, insert, prepare

pytestmark = pytest.mark.django_db(transaction=True)


def test_erasure_removes_unsubmitted_sources_but_retains_independently_submitted_evidence(age_world):
    owner = age_world[0]
    draft, draft_subject = create_subject(age_world, SubjectKind.APPLICATION)
    submitted, submitted_subject = create_subject(age_world, SubjectKind.ROLE_ASSIGNMENT)
    insert(age_world, draft_subject, prepare(age_world, draft_subject))
    insert(age_world, submitted_subject, prepare(age_world, submitted_subject))
    submitted.submitted_at = timezone.now()
    submitted.save(update_fields=["submitted_at"])
    retained = EventAnswerDerivation.objects.get(role_assignment=submitted)
    envelope = retained.source_dob_envelope
    erase_account_vault(owner.pk, actor=owner)
    assert not EventAnswerDerivation.objects.filter(application=draft).exists()
    retained.refresh_from_db()
    assert retained.source_dob_envelope == envelope
    assert PiiAccountWriteFence.objects.get(user=owner).state == "erased"
    erase_account_vault(owner.pk, actor=owner)  # Repeat does not touch retained evidence.
    assert EventAnswerDerivation.objects.filter(pk=retained.pk).exists()


def test_erased_fence_cannot_be_deleted_and_recreated_while_user_exists(age_world):
    owner = age_world[0]
    erase_account_vault(owner.pk, actor=owner)
    fence = PiiAccountWriteFence.objects.get(user=owner)
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM encryption_piiaccountwritefence WHERE user_id=%s", [owner.pk])
        assert cursor.rowcount == 0
    fence.refresh_from_db()
    assert fence.state == "erased"
    with pytest.raises(AccountKeyChanged):
        with account_write(owner.pk):
            pytest.fail("Erased account resumed writing")


def test_failed_domain_cleanup_rolls_back_vault_erasure_and_permanent_fence(age_world, monkeypatch):
    owner = age_world[0]
    from apps.events.profile_photos.erasure import EventSubjectErasure
    def fail(*args, **kwargs):
        raise RuntimeError("Injected domain cleanup failure")
    monkeypatch.setattr(EventSubjectErasure, "erase_locked", fail)
    with pytest.raises(RuntimeError):
        erase_account_vault(owner.pk, actor=owner)
    assert not PiiAccountWriteFence.objects.filter(user=owner, state="erased").exists()


def test_actual_user_deletion_removes_retained_fence_only_after_identity_is_gone(age_world):
    from apps.accounts.models import User
    owner = age_world[0]
    owner_id = owner.pk
    # Host-authorized deletion has no audit actor edge to this test identity.
    erase_account_vault(owner_id, actor=None)
    User.objects.filter(pk=owner_id).delete()
    assert not User.objects.filter(pk=owner_id).exists()
    assert not PiiAccountWriteFence.objects.filter(user_id=owner_id).exists()
