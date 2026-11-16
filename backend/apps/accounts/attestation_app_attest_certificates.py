"""The bounded, pinned App Attest certificate path and Apple nonce extension."""

import hmac

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.x509.oid import ObjectIdentifier
from django.utils import timezone

from apps.accounts.attestation_apple_root import APPLE_APP_ATTEST_ROOT_CA

NONCE_OID = ObjectIdentifier("1.2.840.113635.100.8.2")


def credential_certificate(chain_bytes):
    if not isinstance(chain_bytes, list) or not 2 <= len(chain_bytes) <= 3:
        raise ValueError("Invalid certificate chain")
    if any(not isinstance(value, bytes) or len(value) > 8192 for value in chain_bytes):
        raise ValueError("Invalid certificate")
    chain = [x509.load_der_x509_certificate(value) for value in chain_bytes]
    root = x509.load_pem_x509_certificate(APPLE_APP_ATTEST_ROOT_CA)
    if chain[-1].fingerprint(hashes.SHA256()) == root.fingerprint(hashes.SHA256()):
        chain.pop()
    chain.append(root)
    now = timezone.now()
    for cert in chain:
        if not cert.not_valid_before_utc <= now <= cert.not_valid_after_utc:
            raise ValueError("Certificate outside validity period")
    for index, issuer in enumerate(chain[1:], start=1):
        chain[index - 1].verify_directly_issued_by(issuer)
        constraints = issuer.extensions.get_extension_for_class(x509.BasicConstraints).value
        if not constraints.ca or (constraints.path_length is not None and index - 1 > constraints.path_length):
            raise ValueError("Invalid certificate authority")
        usage = issuer.extensions.get_extension_for_class(x509.KeyUsage).value
        if not usage.key_cert_sign:
            raise ValueError("Invalid certificate signing usage")
    return chain[0]


def verify_nonce(certificate, nonce):
    extension = certificate.extensions.get_extension_for_oid(NONCE_OID).value
    # Apple's DER SEQUENCE { [1] EXPLICIT OCTET STRING (32 bytes) }. Matching the
    # full encoding enforces the ASN.1 structure as well as the nonce value.
    if not isinstance(extension, x509.UnrecognizedExtension) or not hmac.compare_digest(
        extension.value, b"\x30\x24\xa1\x22\x04\x20" + nonce
    ):
        raise ValueError("Certificate nonce mismatch")
