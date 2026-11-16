"""Offline synthetic App Attest chain; this is not a captured Apple fixture."""

import base64
import hashlib
from datetime import timedelta
from types import SimpleNamespace

import cbor2
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID, ObjectIdentifier
from django.utils import timezone

from apps.accounts.attestation import AttestationRejected
from apps.accounts.attestation_app_attest import verify_app_attest

RAW = "synthetic-app-attest-challenge"
TEAM = "TEAMID1234"
APP = "org.spaceworks.app"
NONCE_OID = ObjectIdentifier("1.2.840.113635.100.8.2")


def certificate(name, key, *, issuer=None, issuer_key=None, ca=False, nonce=None, expired=False):
    now = timezone.now()
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
    builder = (x509.CertificateBuilder()
               .subject_name(subject).issuer_name(issuer.subject if issuer else subject)
               .public_key(key.public_key()).serial_number(x509.random_serial_number())
               .not_valid_before(now - timedelta(days=2))
               .not_valid_after(now + timedelta(days=-1 if expired else 2))
               .add_extension(x509.BasicConstraints(ca=ca, path_length=1 if ca else None), critical=True)
               .add_extension(x509.KeyUsage(
                   digital_signature=True, content_commitment=False, key_encipherment=False,
                   data_encipherment=False, key_agreement=False, key_cert_sign=ca,
                   crl_sign=ca, encipher_only=False, decipher_only=False,
               ), critical=True))
    if nonce is not None:
        builder = builder.add_extension(x509.UnrecognizedExtension(
            NONCE_OID, b"\x30\x24\xa1\x22\x04\x20" + nonce,
        ), critical=False)
    return builder.sign(issuer_key or key, hashes.SHA256())


@pytest.fixture
def synthetic_attestation(monkeypatch):
    root_key = ec.generate_private_key(ec.SECP256R1())
    root = certificate("Synthetic App Attest root", root_key, ca=True)
    intermediate_key = ec.generate_private_key(ec.SECP256R1())
    intermediate = certificate("Synthetic App Attest intermediate", intermediate_key,
                               issuer=root, issuer_key=root_key, ca=True)
    leaf_key = ec.generate_private_key(ec.SECP256R1())
    monkeypatch.setattr(
        "apps.accounts.attestation_app_attest_certificates.APPLE_APP_ATTEST_ROOT_CA",
        root.public_bytes(serialization.Encoding.PEM),
    )

    def build(tamper=None, *, environment="development"):
        point = leaf_key.public_key().public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint,
        )
        key_id = hashlib.sha256(point).digest()
        numbers = leaf_key.public_key().public_numbers()
        if tamper == "cose":
            numbers = ec.generate_private_key(ec.SECP256R1()).public_key().public_numbers()
        cose = {1: 2, 3: -7, -1: 1,
                -2: numbers.x.to_bytes(32, "big"), -3: numbers.y.to_bytes(32, "big")}
        rp_id = hashlib.sha256(f"{TEAM}.{APP}".encode()).digest()
        if tamper == "rp_id":
            rp_id = hashlib.sha256(b"ANOTHERTEAM.org.attacker.app").digest()
        aaguid = b"appattestdevelop" if environment == "development" else b"appattest" + b"\0" * 7
        if tamper == "aaguid":
            aaguid = b"appattest" + b"\0" * 7 if environment == "development" else b"appattestdevelop"
        counter = 1 if tamper == "counter" else 0
        cred_id = b"x" * 32 if tamper == "credential_id" else key_id
        auth_data = (rp_id + b"\x40" + counter.to_bytes(4, "big") + aaguid
                     + len(cred_id).to_bytes(2, "big") + cred_id + cbor2.dumps(cose))
        nonce = hashlib.sha256(auth_data + hashlib.sha256(RAW.encode()).digest()).digest()
        if tamper == "nonce":
            nonce = b"n" * 32
        # Re-sign altered authData so every semantic test has a valid nonce binding;
        # otherwise a nonce failure would conceal a missing rpId/counter/COSE check.
        leaf = certificate("Synthetic credential", leaf_key, issuer=intermediate,
                           issuer_key=intermediate_key, nonce=nonce, expired=tamper == "expired")
        chain = [leaf.public_bytes(serialization.Encoding.DER),
                 intermediate.public_bytes(serialization.Encoding.DER)]
        if tamper == "chain":
            unrelated_key = ec.generate_private_key(ec.SECP256R1())
            unrelated = certificate("Untrusted root", unrelated_key, ca=True)
            monkeypatch.setattr(
                "apps.accounts.attestation_app_attest_certificates.APPLE_APP_ATTEST_ROOT_CA",
                unrelated.public_bytes(serialization.Encoding.PEM),
            )
        encoded = cbor2.dumps({"fmt": "apple-appattest", "attStmt": {"x5c": chain},
                               "authData": auth_data})
        if tamper == "trailing_cbor":
            encoded += cbor2.dumps({"extra": True})
        payload = {"type": "app_attest",
                   "key_id": base64.b64encode(b"k" * 32 if tamper == "key_id" else key_id).decode(),
                   "attestation": base64.b64encode(encoded).decode()}
        challenge = SimpleNamespace(platform="apple", signing_identity=TEAM,
                                    app_id=APP, environment=environment)
        pem = leaf_key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()
        return challenge, payload, pem

    return build


@pytest.mark.parametrize("environment", ["development", "production"])
def test_valid_synthetic_app_attest_returns_certified_key_metadata(synthetic_attestation, environment):
    challenge, payload, pem = synthetic_attestation(environment=environment)
    result = verify_app_attest(challenge, RAW, payload)
    assert result.subject == payload["key_id"]
    assert result.metadata == {"key_id": payload["key_id"], "public_key": pem,
                               "signing_identity": TEAM}


@pytest.mark.parametrize("tamper", [
    "rp_id", "counter", "aaguid", "key_id", "credential_id", "nonce", "chain",
    "expired", "cose", "trailing_cbor",
])
def test_app_attest_rejects_each_tampered_binding(synthetic_attestation, tamper):
    challenge, payload, _ = synthetic_attestation(tamper)
    with pytest.raises(AttestationRejected):
        verify_app_attest(challenge, RAW, payload)
