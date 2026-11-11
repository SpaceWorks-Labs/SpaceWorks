import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from apps.backup.main_projection_registry import table_rules
from apps.backup.main_projection_verification import build_expected_ledger
from tests.backup import test_compound_archive_e3 as e3


pytestmark = pytest.mark.django_db(transaction=True)


def test_verification_ledger_digests_each_authority_through_table():
    user = get_user_model().objects.create_user(username="ledger-m2m-e3")
    e3._authority_memberships(user)

    ledger = build_expected_ledger(
        "default", table_rules(), (), sequence_facts=()
    )
    through_models = (
        get_user_model()._meta.get_field("groups").remote_field.through,
        get_user_model()._meta.get_field("user_permissions").remote_field.through,
        Group._meta.get_field("permissions").remote_field.through,
    )
    for model in through_models:
        fact = ledger["tables"][model._meta.db_table]
        assert fact["count"] == model._base_manager.count()
        assert fact["count"] >= 1
        assert len(fact["identity_sha256"]) == 64
        assert len(fact["raw_rows_sha256"]) == 64
