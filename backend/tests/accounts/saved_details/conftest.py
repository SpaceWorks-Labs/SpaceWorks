import json
from pathlib import Path
from uuid import uuid4

from cryptography.fernet import Fernet
import pytest

from apps.accounts.models import User
from apps.accounts.saved_details import fields

FIXTURES = Path(__file__).parents[2] / "events/programme/contracts/fixtures"


class ContractFields:
    """Test double for F's independently owned standard-field validator."""
    def descriptors(self):
        return tuple(json.loads((FIXTURES / "profile-fields-v3.json").read_text())["descriptors"])

    def normalize(self, key, value):
        # These tests exercise account boundaries, not a second form validator.
        if key == "age_at_event" or value in (None, ""):
            raise ValueError()
        return value.strip() if isinstance(value, str) else value


@pytest.fixture
def owner(settings, monkeypatch):
    settings.ACCOUNT_SAVED_DETAILS_ENABLED = True
    settings.ACCOUNT_PII_KEY_BROKER = "local"
    settings.ACCOUNT_PII_MASTER_KEY = Fernet.generate_key().decode()
    settings.ACCOUNT_PII_MASTER_KEY_PREVIOUS = ""
    settings.PII_ENCRYPTION_ENABLED = False
    monkeypatch.setattr(fields, "_provider", ContractFields())
    return User.objects.create_user(username=f"vault-{uuid4().hex}")
