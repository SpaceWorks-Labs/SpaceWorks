from uuid import uuid4

import pytest
from django.db import DatabaseError, connection, transaction
from django.utils import timezone

from apps.accounts.models import User

pytestmark = pytest.mark.django_db


def test_raw_plaintext_cannot_bypass_account_model_mapper():
    owner = User.objects.create_user(username="sql-vault-owner")
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("""INSERT INTO accounts_membersaveddetail
          (id,user_id,field_key,value_envelope,value_type,version,updated_at,save_consent_version,consented_at)
          VALUES (%s,%s,'display_name','plaintext','text',1,%s,1,%s)""",
          [uuid4(), owner.pk, timezone.now(), timezone.now()])


def test_erased_account_fence_cannot_be_reopened_through_sql():
    from apps.encryption.account_models import PiiAccountWriteFence
    owner = User.objects.create_user(username="sql-erased-owner")
    fence = PiiAccountWriteFence.objects.create(user=owner, state="erased", epoch=2)
    with pytest.raises(DatabaseError), transaction.atomic():
        PiiAccountWriteFence.objects.filter(pk=fence.pk).update(state="open", epoch=1)


def test_programme_secrets_have_exact_backup_policy_and_continuity_custody():
    from apps.backup.archive_payload import CONTINUITY_KEYS
    from apps.backup.settings_policy import POLICIES, Policy
    for name in ("ACCOUNT_PII_MASTER_KEY", "ACCOUNT_PII_MASTER_KEY_PREVIOUS",
                 "EVENT_REGISTRATION_CREDENTIAL_DIGEST_KEY", "EVENT_REGISTRATION_CREDENTIAL_KEYS"):
        assert name in CONTINUITY_KEYS
        assert POLICIES[name].policy == Policy.EXACT_FINGERPRINT
        assert POLICIES[name].secret_bearing and POLICIES[name].blocks_restore
