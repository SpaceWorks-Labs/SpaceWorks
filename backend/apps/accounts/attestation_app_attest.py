"""Apple App Attest enrolment: a fresh, challenge-bound key for each new grant."""

import base64
import binascii
import hashlib
import hmac
import io

import cbor2
from cryptography import x509
from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from apps.accounts.attestation import AttestationRejected, VerifiedAttestation
from apps.accounts.attestation_app_attest_certificates import credential_certificate, verify_nonce


def _base64(value, limit):
    if not isinstance(value, str) or not 0 < len(value) <= limit:
        raise ValueError("Invalid base64 value")
    return base64.b64decode(value, validate=True)


def _cbor(raw):
    stream = io.BytesIO(raw)
    value = cbor2.CBORDecoder(stream, max_depth=16, allow_duplicate_keys=False).decode()
    if stream.read(1):
        raise ValueError("Trailing CBOR data")
    return value


def _verify_auth_data(auth_data, challenge, key_id, public_key):
    if not isinstance(auth_data, bytes) or not 55 < len(auth_data) <= 16384:
        raise ValueError("Invalid authenticator data")
    expected_rp = hashlib.sha256(f"{challenge.signing_identity}.{challenge.app_id}".encode()).digest()
    expected_aaguid = b"appattestdevelop" if challenge.environment == "development" else b"appattest" + b"\0" * 7
    credential_length = int.from_bytes(auth_data[53:55], "big")
    if (not hmac.compare_digest(auth_data[:32], expected_rp)
            or not auth_data[32] & 0x40 or auth_data[33:37] != b"\0" * 4
            or auth_data[37:53] != expected_aaguid or credential_length != 32
            or not hmac.compare_digest(auth_data[55:87], key_id)):
        raise ValueError("Authenticator binding failed")
    # App Attest's credential key is EC2/P-256; bind the COSE point to the certified
    # key too, rather than storing an independently supplied authenticator key.
    cose = _cbor(auth_data[87:])
    point = public_key.public_numbers()
    if (cose[1] != 2 or cose[3] != -7 or cose[-1] != 1
            or cose[-2] != point.x.to_bytes(32, "big") or cose[-3] != point.y.to_bytes(32, "big")):
        raise ValueError("Credential public key mismatch")


def verify_app_attest(challenge, raw_challenge, payload):
    try:
        if not isinstance(payload, dict) or payload.get("type") != "app_attest":
            raise ValueError("Invalid attestation type")
        key_id = _base64(payload["key_id"], 64)
        if len(key_id) != 32:
            raise ValueError("Invalid key identifier")
        obj = _cbor(_base64(payload["attestation"], 65536))
        if obj["fmt"] != "apple-appattest":
            raise ValueError("Invalid attestation format")
        certificate = credential_certificate(obj["attStmt"]["x5c"])
        public_key = certificate.public_key()
        if not isinstance(public_key, ec.EllipticCurvePublicKey) or not isinstance(public_key.curve, ec.SECP256R1):
            raise ValueError("Invalid credential key")
        point = public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        if not hmac.compare_digest(hashlib.sha256(point).digest(), key_id):
            raise ValueError("Key identifier mismatch")
        auth_data = obj["authData"]
        _verify_auth_data(auth_data, challenge, key_id, public_key)
        nonce = hashlib.sha256(auth_data + hashlib.sha256(raw_challenge.encode()).digest()).digest()
        verify_nonce(certificate, nonce)
        pem = public_key.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    except (ValueError, TypeError, KeyError, IndexError, AttributeError, binascii.Error,
            cbor2.CBORDecodeError, RecursionError, InvalidSignature, UnsupportedAlgorithm,
            x509.ExtensionNotFound, x509.DuplicateExtension) as exc:
        raise AttestationRejected("Attestation was rejected.") from exc
    canonical_key_id = base64.b64encode(key_id).decode()
    return VerifiedAttestation(subject=canonical_key_id, metadata={"key_id": canonical_key_id, "public_key": pem})
