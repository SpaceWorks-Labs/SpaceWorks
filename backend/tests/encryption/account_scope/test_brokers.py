from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet

from apps.encryption import account_readiness as readiness
from apps.encryption.account_checks import check_account_pii_configuration


@pytest.fixture
def configured(settings):
    settings.PII_ENCRYPTION_ENABLED = False
    settings.ACCOUNT_SAVED_DETAILS_ENABLED = True
    settings.ACCOUNT_PII_KEY_BROKER = "local"
    settings.ACCOUNT_PII_MASTER_KEY = Fernet.generate_key().decode()
    settings.ACCOUNT_PII_MASTER_KEY_PREVIOUS = ""
    return settings


def test_readiness_independent_of_tenant_flag_and_local_account_binding(configured):
    assert readiness.assert_ready()
    broker = readiness.get_broker()
    wrapped = broker.create_dek(17, 1)
    assert broker.unwrap_dek(wrapped.wrapped_dek, 17, 1) == wrapped.dek
    for owner, version in ((18, 1), (17, 2)):
        with pytest.raises(readiness.SavedDetailsUnavailable):
            broker.unwrap_dek(wrapped.wrapped_dek, owner, version)


def test_missing_key_is_actionable_even_with_tenant_encryption_disabled(configured):
    configured.ACCOUNT_PII_MASTER_KEY = ""
    assert [error.id for error in check_account_pii_configuration()] == ["encryption.E101"]
    with pytest.raises(readiness.SavedDetailsUnavailable):
        readiness.assert_ready()


def test_tenant_key_reuse_is_rejected(configured):
    configured.PII_MASTER_KEY = configured.ACCOUNT_PII_MASTER_KEY
    assert [error.id for error in check_account_pii_configuration()] == ["encryption.E101"]


def test_local_previous_wrapping_key_preserves_custody(configured):
    first = readiness.get_broker().create_dek(17, 2)
    configured.ACCOUNT_PII_MASTER_KEY_PREVIOUS = configured.ACCOUNT_PII_MASTER_KEY
    configured.ACCOUNT_PII_MASTER_KEY = Fernet.generate_key().decode()
    assert readiness.get_broker().unwrap_dek(first.wrapped_dek, 17, 2) == first.dek


def test_kms_context_is_account_scoped_and_probe_failure_fails_closed(configured, monkeypatch):
    assert readiness.AccountKmsBroker._context(17, 2) == {
        "application": "spaceworks-account-pii-v1", "account_id": "17", "dek_version": "2",
    }
    monkeypatch.setattr(readiness, "get_broker", lambda: SimpleNamespace(
        create_dek=lambda *_: (_ for _ in ()).throw(TimeoutError())))
    with pytest.raises(readiness.SavedDetailsUnavailable):
        readiness.assert_ready()
