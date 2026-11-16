from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from django.db import DatabaseError, connection, transaction
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.saved_details.models import MemberSavedDetail
from apps.encryption.account_crypto import decrypt, encrypt
from apps.encryption.account_mappers import account_key_context
from apps.encryption.account_services import get_account_key, prepare_account_key, rotate_account_key
from apps.encryption.account_write_fence import (
    AccountKeyChanged, account_fences, account_write, verify_prepared_epoch,
)
from apps.encryption.crypto import PiiAuthenticationFailed, PiiMalformedEnvelope
from apps.encryption.models import PiiGlobalWriteFence
from apps.encryption.write_fence import PiiWriteFenced

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def context(settings):
    settings.ACCOUNT_SAVED_DETAILS_ENABLED = True
    settings.ACCOUNT_PII_KEY_BROKER = "local"
    settings.ACCOUNT_PII_MASTER_KEY = Fernet.generate_key().decode()
    settings.ACCOUNT_PII_MASTER_KEY_PREVIOUS = ""
    settings.PII_ENCRYPTION_ENABLED = False
    owner = User.objects.create_user(username=f"saved-{uuid4().hex}")
    return owner, prepare_account_key(owner.pk)


def _detail(owner):
    return MemberSavedDetail(user=owner, field_key="date_of_birth", value_type="date",
                             value_envelope="2000-02-29", consented_at=timezone.now())


def test_plaintext_and_bulk_write_refused_even_when_tenant_pii_disabled(context):
    owner, key = context
    row = _detail(owner)
    with account_write(owner.pk), account_key_context(key):
        with pytest.raises(PiiMalformedEnvelope):
            row.save()
    with pytest.raises(RuntimeError, match="require"):
        MemberSavedDetail.objects.bulk_create([row])
    with pytest.raises(RuntimeError, match="require"):
        MemberSavedDetail.objects.filter(user=owner).update(value_envelope="plaintext")
    with pytest.raises(RuntimeError, match="require"):
        MemberSavedDetail.objects.filter(user=owner).update(user_id=owner.pk + 1)


def test_model_raw_attribute_remains_ciphertext_and_cross_row_copy_fails(context):
    owner, key = context
    row = _detail(owner)
    row.value_envelope = encrypt(b'"2000-02-29"', key.dek, key_version=key.version,
        user_id=owner.pk, table=row._meta.db_table, pk=row.pk, field="value_envelope")
    with account_write(owner.pk), account_key_context(key):
        row.save()
    assert MemberSavedDetail.objects.get(pk=row.pk).value_envelope.startswith("pii:account:")
    assert "2000-02-29" not in row.value_envelope
    substituted = _detail(owner)
    substituted.value_envelope = row.value_envelope
    with account_write(owner.pk), account_key_context(key), pytest.raises(PiiAuthenticationFailed):
        substituted.save()
    with pytest.raises(RuntimeError, match="Declare the account fence"):
        row.save(update_fields=["version"])


def test_profile_key_cannot_relabel_sensitive_ciphertext(context):
    owner, key = context
    row = _detail(owner)
    row.value_envelope = encrypt(b'"2000-02-29"', key.dek, key_version=key.version,
        user_id=owner.pk, table=row._meta.db_table, pk=row.pk, field="value_envelope")
    with account_write(owner.pk), account_key_context(key):
        row.save()
        row.field_key = "name"
        from apps.encryption.crypto import PiiUnavailable
        with pytest.raises(PiiUnavailable, match="immutable"):
            row.save()
    with pytest.raises(RuntimeError):
        MemberSavedDetail.objects.filter(pk=row.pk).update(field_key="name")


def test_global_maintenance_blocks_account_without_tenant_dependency(context):
    owner, _ = context
    PiiGlobalWriteFence.objects.filter(pk=1).update(state="closed", operation_id=uuid4())
    with pytest.raises(PiiWriteFenced):
        with account_write(owner.pk):
            pytest.fail("Closed global fence admitted a write")


def test_fences_refuse_scope_expansion_after_domain_command_begins(context):
    owner, _ = context
    with account_write(owner.pk):
        with pytest.raises(RuntimeError, match="Cannot expand"):
            with account_fences([owner.pk, owner.pk + 1]):
                pass


def test_intent_epoch_check_never_takes_account_or_user_row_locks(context):
    owner, key = context
    with account_write(owner.pk), CaptureQueriesContext(connection) as queries:
        verify_prepared_epoch(owner.pk, key.epoch, key.version)
    assert queries.captured_queries
    assert all("FOR UPDATE" not in query["sql"].upper() for query in queries.captured_queries)


def test_raw_plaintext_write_is_rejected_by_database_backstop(context):
    """G's migration must enforce this even when a caller bypasses the mapper."""
    owner, key = context
    row = _detail(owner)
    row.value_envelope = encrypt(b'"2000-02-29"', key.dek, key_version=key.version,
        user_id=owner.pk, table=row._meta.db_table, pk=row.pk, field="value_envelope")
    with account_write(owner.pk), account_key_context(key):
        row.save()
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("UPDATE accounts_membersaveddetail SET value_envelope=%s WHERE id=%s",
                       ["2000-02-29", row.pk])


def test_rotation_invalidates_intent_epoch_but_retains_old_ciphertext_custody(context):
    owner, first = context
    row_id = uuid4()
    binding = {"user_id": owner.pk, "table": "accounts_membersaveddetail",
               "pk": row_id, "field": "value_envelope"}
    encrypted = encrypt(b"private", first.dek, key_version=first.version, **binding)
    second = rotate_account_key(owner.pk, owner)
    assert second.version == first.version + 1
    assert second.epoch == first.epoch + 1
    old = get_account_key(owner.pk, first.version)
    assert old.dek == first.dek
    assert old.epoch == second.epoch
    assert decrypt(encrypted, old.dek, **binding) == b"private"
    with account_write(owner.pk), pytest.raises(AccountKeyChanged):
        verify_prepared_epoch(owner.pk, first.epoch, first.version)
