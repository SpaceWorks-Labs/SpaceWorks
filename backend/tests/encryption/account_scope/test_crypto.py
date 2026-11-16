from uuid import uuid4

import pytest

from apps.encryption.account_crypto import decrypt, encrypt, envelope_version, parse_envelope
from apps.encryption.crypto import PiiAuthenticationFailed, PiiMalformedEnvelope


@pytest.fixture
def binding():
    return {"user_id": 17, "table": "accounts_membersaveddetail", "pk": uuid4(),
            "field": "value_envelope"}


def test_account_envelope_encrypts_even_empty_value_and_never_tenant_prefix(binding):
    first = encrypt(b"", b"k" * 32, key_version=3, **binding)
    second = encrypt(b"", b"k" * 32, key_version=3, **binding)
    assert first.startswith("pii:account:gcm:v1:3:")
    assert first != second
    assert envelope_version(first) == 3
    assert decrypt(first, b"k" * 32, **binding) == b""


@pytest.mark.parametrize("change", [
    {"user_id": 18}, {"table": "accounts_saveddetailupdateintent"},
    {"pk": uuid4()}, {"field": "encrypted_payload"},
])
def test_owner_row_table_field_substitution_fails_authentication(binding, change):
    envelope = encrypt(b'{"dob":"2000-02-29"}', b"k" * 32, key_version=1, **binding)
    with pytest.raises(PiiAuthenticationFailed):
        decrypt(envelope, b"k" * 32, **(binding | change))


@pytest.mark.parametrize("value", ["plaintext", "", "pii:gcm:v1:1:abc:def",
    "pii:account:gcm:v1:01:AAAAAAAAAAAAAAAA:AAAAAAAAAAAAAAAAAAAAAA",
    "pii:account:gcm:v1:1:AAAAAAAAAAAAAAAA:AAAAAAAAAAAAAAAAAAAAAB"])
def test_account_envelope_never_accepts_legacy_or_malformed_plaintext(value):
    with pytest.raises(PiiMalformedEnvelope):
        parse_envelope(value)
