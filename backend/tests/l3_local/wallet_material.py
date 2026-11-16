"""Throw-away wallet signing material generated in the test (never a real key, never committed)."""
import base64
import json
from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

PASS_TYPE, TEAM = "pass.test.spaceworks", "TEAM123456"


def _key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _name(common, extra=None):
    attrs = [x509.NameAttribute(NameOID.COMMON_NAME, common)]
    attrs += [x509.NameAttribute(oid, value) for oid, value in (extra or {}).items()]
    return x509.Name(attrs)


def _cert(subject, issuer, key, signer, *, days=365, ca=False):
    now = datetime.now(timezone.utc)
    return (x509.CertificateBuilder().subject_name(subject).issuer_name(issuer).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(days=1))
            .not_valid_after(now + timedelta(days=days))
            .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True)
            .sign(signer, hashes.SHA256()))


def pem(cert):
    return cert.public_bytes(serialization.Encoding.PEM).decode()


def key_pem(key, password=None):
    enc = serialization.BestAvailableEncryption(password) if password else serialization.NoEncryption()
    return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, enc).decode()


def apple_material(pass_type=PASS_TYPE, team=TEAM, *, days=365):
    """`{cert_pem, key_pem, wwdr_pem, ...}` for a Pass Type ID certificate signed by a throw-away WWDR CA."""
    ca_key, key = _key(), _key()
    ca_name = _name("Test WWDR CA")
    ca = _cert(ca_name, ca_name, ca_key, ca_key, ca=True)
    subject = _name("Pass Type ID: " + pass_type, {NameOID.USER_ID: pass_type, NameOID.ORGANIZATIONAL_UNIT_NAME: team})
    cert = _cert(subject, ca_name, key, ca_key, days=days)
    return {"apple_pass_type_id": pass_type, "apple_team_id": team, "apple_cert_pem": pem(cert),
            "apple_key_pem": key_pem(key), "apple_wwdr_pem": pem(ca), "_cert": cert, "_key": key, "_ca": ca}


def apple_p12(material, password=b"pw"):
    blob = pkcs12.serialize_key_and_certificates(b"pass", material["_key"], material["_cert"], [material["_ca"]],
                                                 serialization.BestAvailableEncryption(password))
    return base64.b64encode(blob).decode()


def google_material(issuer="3388000000012345678"):
    key = _key()
    account = {"type": "service_account", "client_email": "wallet@test-project.iam.gserviceaccount.com",
               "private_key": key_pem(key)}
    return {"google_issuer_id": issuer, "google_service_account": json.dumps(account), "_key": key}


def public_fields(material):
    return {k: v for k, v in material.items() if not k.startswith("_")}
