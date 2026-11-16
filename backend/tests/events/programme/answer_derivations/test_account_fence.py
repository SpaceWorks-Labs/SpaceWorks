"""Prepare-to-erase serialization applies even without a vault save intent."""

from dataclasses import replace

import pytest
from django.db import connection, transaction

from apps.encryption.account_models import AccountPiiKey, PiiAccountWriteFence
from apps.encryption.account_write_fence import ACCOUNT_LOCK_NAMESPACE
from apps.encryption.write_fence import PiiWriteFenced
from apps.events.answer_derivations.models import EventAnswerDerivation
from apps.events.answer_derivations.workflow import insert_prepared_locked
from apps.events.contracts.providers import LockedContext
from apps.events.contracts.subjects import SubjectKind

from .conftest import create_subject, insert, locked, prepare

pytestmark = pytest.mark.django_db(transaction=True)


def test_inline_source_without_vault_still_holds_real_shared_account_lock(age_world, settings, allow_projection_databases):
    settings.ACCOUNT_SAVED_DETAILS_ENABLED = False
    settings.ACCOUNT_PII_MASTER_KEY = ""
    owner = age_world[0]
    _, subject = create_subject(age_world, SubjectKind.ROLE_ASSIGNMENT)
    prepared = prepare(age_world, subject)
    assert not AccountPiiKey.objects.filter(user=owner).exists()
    assert not PiiAccountWriteFence.objects.filter(user=owner).exists()
    with locked(age_world, subject) as locks:
        # A second PostgreSQL session cannot take the exclusive erasure lock
        # while the event insertion's shared account fence is held.
        probe = connection.copy()  # a second PostgreSQL session on the same alias
        try:
            with probe.cursor() as cursor:
                cursor.execute("SELECT pg_try_advisory_lock(%s, %s)", [ACCOUNT_LOCK_NAMESPACE, owner.pk])
                acquired = cursor.fetchone()[0]
                if acquired:
                    cursor.execute("SELECT pg_advisory_unlock(%s, %s)", [ACCOUNT_LOCK_NAMESPACE, owner.pk])
                assert acquired is False
        finally:
            probe.close()
        insert_prepared_locked(prepared, actor_id=owner.pk, subject=subject, locks=locks,
                               form_sha256="a" * 64, canonical_answer_sha256="b" * 64)
    assert not AccountPiiKey.objects.filter(user=owner).exists()
    assert not PiiAccountWriteFence.objects.filter(user=owner).exists()


def test_claimed_locked_context_without_real_account_fence_refuses(age_world):
    owner, _, space, event = age_world
    _, subject = create_subject(age_world, SubjectKind.ROLE_ASSIGNMENT)
    prepared = prepare(age_world, subject)
    claimed = LockedContext(event_id=event.pk, tenant_ids=(space.pk,), account_ids=(owner.pk,))
    with transaction.atomic(), pytest.raises(RuntimeError, match="account fence"):
        insert_prepared_locked(prepared, actor_id=owner.pk, subject=subject, locks=claimed,
                               form_sha256="a" * 64, canonical_answer_sha256="b" * 64)
    with locked(age_world, subject) as locks, pytest.raises(RuntimeError, match="account fence"):
        insert_prepared_locked(prepared, actor_id=owner.pk, subject=subject,
                               locks=replace(locks, account_ids=()), form_sha256="a" * 64,
                               canonical_answer_sha256="b" * 64)
    assert not EventAnswerDerivation.objects.filter(event=event).exists()


@pytest.mark.parametrize("state", ["closed", "erased"])
def test_prepare_then_closed_or_erased_fence_refuses_before_event_insert(age_world, state):
    owner = age_world[0]
    _, subject = create_subject(age_world, SubjectKind.ROLE_ASSIGNMENT)
    prepared = prepare(age_world, subject)
    PiiAccountWriteFence.objects.create(user=owner, state=state, epoch=2)
    # A closed fence refuses as fenced; an erased epoch is "account_key_changed" (§10A),
    # exactly as the live-erasure recheck below.
    from apps.events.answer_derivations.errors import DerivationError
    with pytest.raises(PiiWriteFenced if state == "closed" else DerivationError) as refused:
        insert(age_world, subject, prepared)
    if state == "erased":
        assert refused.value.detail["code"] == "account_key_changed"
    assert not EventAnswerDerivation.objects.filter(event_id=subject.event_id).exists()


def test_live_erasure_state_is_rechecked_even_with_an_existing_fence_context(age_world):
    from apps.events.answer_derivations.errors import DerivationError

    owner = age_world[0]
    _, subject = create_subject(age_world, SubjectKind.ROLE_ASSIGNMENT)
    prepared = prepare(age_world, subject)
    with locked(age_world, subject) as locks:
        # Emulate a reviewed maintenance command changing persistent state in
        # its already-held account context. The assertion alone is insufficient.
        PiiAccountWriteFence.objects.create(user=owner, state="erased", epoch=2)
        with pytest.raises(DerivationError) as caught:
            insert_prepared_locked(prepared, actor_id=owner.pk, subject=subject, locks=locks,
                                   form_sha256="a" * 64, canonical_answer_sha256="b" * 64)
        assert caught.value.status_code == 409
        assert caught.value.detail["code"] == "account_key_changed"
    assert not EventAnswerDerivation.objects.filter(event_id=subject.event_id).exists()
