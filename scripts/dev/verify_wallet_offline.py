#!/usr/bin/env python
"""Prove the wallet-pass code works with NO Apple or Google account (decision 223(l)).

It generates throw-away signing material, drives the REAL parser and builders from
`backend/apps/card_designs/wallet/`, then checks the output independently of that code:
  Apple : parse_apple accepts/rejects, .pkpass unzips, manifest SHA-1s match, the detached
          PKCS#7 signature verifies against the manifest and the generated chain (openssl,
          when present), pass.json carries no e-mail / phone / birth date, guest passes are static.
  Google: parse_google accepts/rejects, the save-link JWT verifies with the RSA public key and
          carries iss / aud "google" / typ "savetowallet" / origins / object ids and no PII.
No database, no network, nothing written outside a temp dir. Needs: django, djangorestframework,
cryptography, reportlab, Pillow, pypdfium2 (all in backend/requirements.txt).

Run on the host (any venv with those packages):   python scripts/dev/verify_wallet_offline.py
Run in the dev stack (copy it in, the repo scripts/ folder is not mounted):
    docker compose cp scripts/dev/verify_wallet_offline.py backend:/tmp/verify_wallet_offline.py
    docker compose exec backend python /tmp/verify_wallet_offline.py
Exit code 0 = every check passed. It is NOT proof Apple/Google accept the pass; see docs/wallet-passes.md.
"""
import base64
import hashlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for candidate in (ROOT / "backend", Path("/app"), Path.cwd()):
    if (candidate / "apps" / "card_designs" / "wallet").is_dir():
        sys.path.insert(0, str(candidate))
        break

import django  # noqa: E402
from django.conf import settings  # noqa: E402

if not settings.configured:
    settings.configure(USE_TZ=True, SECRET_KEY="offline-verify", PUBLIC_API_BASE_URL="https://example.test",
                       INSTALLED_APPS=["rest_framework"])
    django.setup()

from cryptography import x509  # noqa: E402
from cryptography.hazmat.primitives import hashes, serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import padding, rsa  # noqa: E402
from cryptography.x509.oid import NameOID  # noqa: E402
from rest_framework.exceptions import ValidationError  # noqa: E402

from apps.card_designs.wallet import apple, credential_parsing as parsing, google  # noqa: E402
from apps.card_designs.wallet.credentials import AppleCredentials, GoogleCredentials  # noqa: E402

PASS_TYPE, TEAM = "pass.test.spaceworks", "TEAM123456"
PII = ("ada@example.test", "+1 555 0100", "1990-01-01", "birth", "phone", "email")
results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(("PASS  " if ok else "FAIL  ") + name + (f"  [{detail}]" if detail else ""))


def keypair():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def make_cert(subject, issuer, key, signer, *, days=365, ca=False):
    now = datetime.now(timezone.utc)
    return (x509.CertificateBuilder().subject_name(subject).issuer_name(issuer).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(days=max(abs(days) + 1, 1)))
            .not_valid_after(now + timedelta(days=days))
            .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True)
            .sign(signer, hashes.SHA256()))


def pem(cert):
    return cert.public_bytes(serialization.Encoding.PEM).decode()


def key_pem(key):
    return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                             serialization.NoEncryption()).decode()


def refused(func, field):
    try:
        func()
    except ValidationError as exc:
        text = json.dumps(exc.detail)
        return field in exc.detail and "PRIVATE KEY" not in text
    return False


def member_content():
    return {"issuer": "Test Makerspace", "name": "Ada Lovelace", "number": "M-000042", "label": "Plan",
            "label_value": "Maker", "valid_until": "31 Dec 2027", "qr": "SW1:desk:abc123", "standing": "valid"}


def guest_content():  # same shape as wallet/guest.py:content()
    return {"issuer": "Test Makerspace", "name": "Guest", "number": "GP-000007", "label": "Pass",
            "label_value": "Day pass", "valid_until": "01 Jan 2027 18:00", "qr": "gp1.7.deadbeef", "standing": "valid",
            "description": "guest pass", "expires_at": "2027-01-01T18:00:00+00:00"}


def openssl_verify(tmp, signature, manifest, ca_pem):
    exe = shutil.which("openssl")
    if not exe:
        return None, "openssl not on PATH (signature structure checked only)"
    (tmp / "sig.der").write_bytes(signature)
    (tmp / "manifest.json").write_bytes(manifest)
    (tmp / "ca.pem").write_text(ca_pem)
    proc = subprocess.run([exe, "smime", "-verify", "-binary", "-inform", "DER", "-in", str(tmp / "sig.der"),
                           "-content", str(tmp / "manifest.json"), "-CAfile", str(tmp / "ca.pem"), "-purpose", "any",
                           "-out", str(tmp / "out.bin")], capture_output=True, text=True)
    return proc.returncode == 0, (proc.stdout + proc.stderr).strip()[:120]


def verify_pkpass(label, blob, creds, ca_pem, tmp, *, static):
    archive = zipfile.ZipFile(io.BytesIO(blob))
    names = set(archive.namelist())
    check(f"{label}: archive has pass.json, manifest, signature, icons",
          {"pass.json", "manifest.json", "signature", "icon.png", "icon@2x.png", "logo.png"} <= names)
    manifest_raw = archive.read("manifest.json")
    manifest = json.loads(manifest_raw)
    check(f"{label}: manifest lists every payload file", set(manifest) == names - {"manifest.json", "signature"})
    check(f"{label}: every manifest SHA-1 matches",
          all(hashlib.sha1(archive.read(n)).hexdigest() == d for n, d in manifest.items()))
    ok, detail = openssl_verify(tmp, archive.read("signature"), manifest_raw, ca_pem)
    if ok is None:
        from cryptography.hazmat.primitives.serialization import pkcs7
        check(f"{label}: PKCS#7 parses with signer + WWDR certs",
              len(pkcs7.load_der_pkcs7_certificates(archive.read("signature"))) == 2, detail)
    else:
        check(f"{label}: detached PKCS#7 verifies against manifest + chain (openssl)", ok, detail)
        bad, _ = openssl_verify(tmp, archive.read("signature"), manifest_raw.replace(b"pass.json", b"pass.jsoN", 1), ca_pem)
        check(f"{label}: a tampered manifest FAILS verification", bad is False)
    body = json.loads(archive.read("pass.json"))
    text = archive.read("pass.json").decode().lower()
    check(f"{label}: pass.json has the Pass Type ID and Team ID",
          body["passTypeIdentifier"] == creds.pass_type_id and body["teamIdentifier"] == creds.team_id)
    check(f"{label}: no e-mail / phone / birth date in pass.json", not any(p.lower() in text for p in PII))
    if static:
        shape = "webServiceURL" not in body and "authenticationToken" not in body and bool(body.get("expirationDate"))
    else:
        shape = "webServiceURL" in body and "authenticationToken" in body
    check(f"{label}: " + ("static (no web service, has expiry)" if static else "updatable (web service + token)"), shape)


def apple_checks(tmp):
    ca_key, key = keypair(), keypair()
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Throwaway WWDR CA")])
    ca = make_cert(ca_name, ca_name, ca_key, ca_key, ca=True)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Pass Type ID: " + PASS_TYPE),
                         x509.NameAttribute(NameOID.USER_ID, PASS_TYPE),
                         x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, TEAM)])
    cert = make_cert(subject, ca_name, key, ca_key)
    data = {"apple_pass_type_id": PASS_TYPE, "apple_team_id": TEAM, "apple_cert_pem": pem(cert),
            "apple_key_pem": key_pem(key), "apple_wwdr_pem": pem(ca)}
    stored = parsing.parse_apple(data, {})
    check("apple parser: accepts a matching Pass Type ID cert + key + WWDR",
          stored["pass_type_id"] == PASS_TYPE and len(stored["fingerprint"]) == 64)
    check("apple parser: refuses a wrong Pass Type ID", refused(
        lambda: parsing.parse_apple({**data, "apple_pass_type_id": "pass.other"}, {}), "apple_pass_type_id"))
    check("apple parser: refuses a wrong Team ID", refused(
        lambda: parsing.parse_apple({**data, "apple_team_id": "OTHERTEAM1"}, {}), "apple_team_id"))
    check("apple parser: refuses a key that does not match", refused(
        lambda: parsing.parse_apple({**data, "apple_key_pem": key_pem(keypair())}, {}), "apple_key_pem"))
    old = make_cert(subject, ca_name, key, ca_key, days=-2)
    check("apple parser: refuses an expired certificate", refused(
        lambda: parsing.parse_apple({**data, "apple_cert_pem": pem(old)}, {}), "apple_cert_pem"))
    creds = AppleCredentials(PASS_TYPE, TEAM, stored["cert"].encode(), stored["key"].encode(),
                             stored["wwdr"].encode(), "offline")
    wallet_pass = type("P", (), {"voided_at": None})()
    verify_pkpass("member card", apple.build_pkpass_bytes(creds, "serial-1", member_content(), wallet_pass=wallet_pass),
                  creds, pem(ca), tmp, static=False)
    verify_pkpass("guest pass", apple.build_pkpass_bytes(creds, "gp-7-abc", guest_content()), creds, pem(ca), tmp,
                  static=True)
    revoked = json.loads(apple.pass_json(creds, "s", {**member_content(), "standing": "revoked"}))
    check("apple: a revoked holder's pass is marked voided", revoked.get("voided") is True)


def b64d(part):
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


def rs256_ok(public, head, body, sig, suffix=""):
    try:
        public.verify(b64d(sig), f"{head}.{body}{suffix}".encode(), padding.PKCS1v15(), hashes.SHA256())
        return True
    except Exception:  # noqa: BLE001 - any failure means "does not verify"
        return False


def google_checks():
    key = keypair()
    account = {"type": "service_account", "client_email": "wallet@offline-test.iam.gserviceaccount.com",
               "private_key": key_pem(key)}
    data = {"google_issuer_id": "3388000000012345678", "google_service_account": json.dumps(account)}
    stored = parsing.parse_google(data, {})
    check("google parser: accepts issuer id + service-account JSON", stored["class_prefix"] == "spaceworks_card")
    check("google parser: refuses a non-numeric issuer id", refused(
        lambda: parsing.parse_google({**data, "google_issuer_id": "abc"}, {}), "google_issuer_id"))
    check("google parser: refuses a malformed key file", refused(
        lambda: parsing.parse_google({**data, "google_service_account": "{}"}, {}), "google_service_account"))
    creds = GoogleCredentials(stored["issuer_id"], stored["class_prefix"], account["client_email"],
                              account["private_key"], "offline")
    prefix = "https://pay.google.com/gp/v/save/"
    for label, content, serial in (("member card", member_content(), "serial_1"),
                                   ("guest pass", guest_content(), "gp_7_abc")):
        link = google.link_for(creds, serial, content)
        check(f"google {label}: link has the Save-to-Wallet prefix", link.startswith(prefix))
        head, body, sig = link[len(prefix):].split(".")
        public = key.public_key()
        check(f"google {label}: RS256 signature verifies with the public key",
              rs256_ok(public, head, body, sig) and json.loads(b64d(head))["alg"] == "RS256")
        check(f"google {label}: a tampered payload FAILS verification", not rs256_ok(public, head, body, sig, "x"))
        claims = json.loads(b64d(body))
        obj = claims["payload"]["genericObjects"][0]
        check(f"google {label}: claims iss/aud/typ/origins", claims["iss"] == creds.client_email
              and claims["aud"] == "google" and claims["typ"] == "savetowallet" and claims["origins"] == [])
        check(f"google {label}: object + class ids are issuer-scoped",
              obj["id"] == f"{creds.issuer_id}.{serial}" and obj["classId"] == creds.class_id
              and claims["payload"]["genericClasses"][0]["id"] == creds.class_id)
        check(f"google {label}: no e-mail / phone / birth date",
              not any(p.lower() in json.dumps(claims).lower() for p in PII))
    voided_link = google.link_for(creds, "s", member_content(), voided=True)[len(prefix):]
    voided = json.loads(b64d(voided_link.split(".")[1]))
    check("google: a voided pass is INACTIVE", voided["payload"]["genericObjects"][0]["state"] == "INACTIVE")


def main():
    with tempfile.TemporaryDirectory() as raw:
        apple_checks(Path(raw))
    google_checks()
    print(f"\n{sum(results)}/{len(results)} checks passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
