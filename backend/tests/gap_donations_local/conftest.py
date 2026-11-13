"""Gap RP-3 local tests: a throwaway PII master key (the 80G PAN is always encrypted)."""

import pytest
from cryptography.fernet import Fernet


@pytest.fixture(autouse=True)
def pii_keys(settings):
    from apps.encryption.cache import dek_cache

    settings.PII_ENCRYPTION_ENABLED = False
    settings.PII_KEY_BROKER = "local"
    settings.PII_MASTER_KEY = Fernet.generate_key().decode()
    settings.PII_SEARCH_HASH_KEY = ""
    dek_cache.clear()
    yield
    dek_cache.clear()
