"""Real registration/privacy boundaries, with object/KMS I/O only at its edge."""
import base64
from uuid import uuid4

import pytest
from django.db import connection, transaction
from rest_framework.exceptions import ValidationError

from apps.events import services
from apps.events.models import EventRegistration
from apps.events.credentials.models import EventRegistrationCredential
from apps.encryption.crypto import is_envelope
from apps.encryption.account_models import PiiAccountWriteFence
from apps.encryption.account_write_fence import account_write, AccountKeyChanged
from apps.events.services_write_boundary import write_boundary
from tests.events.ticketing_helpers import account, event_space, open_event, signup
from tests.encryption.conftest import enabled_encryption

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def world(settings):
    settings.EVENT_REGISTRATION_CREDENTIAL_KEY_VERSION = 1
    settings.EVENT_REGISTRATION_CREDENTIAL_KEYS = {"1": base64.b64encode(b"g" * 32).decode()}
    settings.EVENT_REGISTRATION_CREDENTIAL_DIGEST_KEY = base64.b64encode(b"d" * 32).decode()
    tag = uuid4().hex[:8]
    event = open_event(event_space("gf4-" + tag), custom_form={"schema_version": 2,
        "form_id": "ordinary", "revision": 1, "questions": []})
    return event, account("gf4-owner-" + tag)


def payload(**values):
    return {"form": {"schema_version": 2, "form_id": "ordinary", "revision": 1},
            "operation_id": str(uuid4()), "answers": {}, **values}


def test_ordinary_v2_http_creates_real_canonical_registration_and_one_badge(world):
    event, owner = world
    response = signup(event, owner, **payload())
    assert response.status_code == 201, response.data
    row = EventRegistration.objects.get(event=event, member=owner)
    assert row.custom_answers == {"version": 2, "form_id": "ordinary", "form_revision": 1, "answers": []}
    assert row.credential_mode == "v2"
    assert EventRegistrationCredential.objects.filter(registration=row, revoked_at=None).count() == 1
    assert signup(event, owner, **payload()).status_code == 201
    assert EventRegistrationCredential.objects.filter(registration=row).count() == 1


def test_duplicate_raw_spellings_refuse_even_when_both_empty(world):
    event, owner = world
    response = signup(event, owner, **payload(custom_answers={}))
    assert response.status_code == 400
    assert not EventRegistration.objects.filter(event=event).exists()


def test_private_documents_and_contacts_are_envelopes_without_locked_broker_refill(world, monkeypatch):
    event, owner = world
    from apps.encryption import services as keys
    from apps.events.programme_locks import _scopes
    original = keys.unwrap_dek
    def unwrap(row):
        assert _scopes.get() is None, "Broker work occurred after programme fences/Event lock"
        return original(row)
    monkeypatch.setattr(keys, "unwrap_dek", unwrap)
    with enabled_encryption():
        row = services.register(event, member=owner, actor=owner, form_payload=payload())
        raw = EventRegistration.objects.values("name", "email", "phone", "custom_answers").get(pk=row.pk)
        assert all(is_envelope(value) for value in raw.values())
        assert row.custom_answers["version"] == 2


def test_erased_historical_owner_does_not_block_event_but_nested_vault_write_refuses(world):
    event, owner = world
    row = services.register(event, member=owner, actor=owner, form_payload=payload())
    PiiAccountWriteFence.objects.update_or_create(user=owner, defaults={"state": "erased"})
    with write_boundary(event):
        EventRegistration.objects.filter(pk=row.pk).update(calendar_sequence=1)
        with pytest.raises(AccountKeyChanged):
            with account_write(owner.pk):
                pytest.fail("Erased account resumed vault writes")
    row.refresh_from_db()
    assert row.calendar_sequence == 1


def test_missing_badge_keys_rolls_back_registration(world, settings):
    event, owner = world
    settings.EVENT_REGISTRATION_CREDENTIAL_KEYS = {}
    from apps.events.credentials.errors import CredentialKeyUnavailable
    with pytest.raises(CredentialKeyUnavailable):
        services.register(event, member=owner, actor=owner, form_payload=payload())
    assert not EventRegistration.objects.filter(event=event).exists()
