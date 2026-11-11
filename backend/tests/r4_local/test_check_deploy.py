"""R4 production gate: `manage.py check --deploy` with the full-VPS (Caddy TLS) settings.

Runs Django in a subprocess so the production values are read at settings import, exactly
as a deployment reads them. The output lands next to this file for the report. Local only."""

import base64
import os
import re
import secrets
import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).with_name("check_deploy_output.txt")
BACKEND = Path(__file__).resolve().parents[2]

PRODUCTION = {
    "DEBUG": "False",
    "SECRET_KEY": secrets.token_urlsafe(64),
    "ALLOWED_HOSTS": "spaces.example.org",
    "ENABLE_HTTPS": "True",
    "TRUST_X_FORWARDED_PROTO": "True",
    "TRUSTED_PROXY_COUNT": "1",
    "AUTH_COOKIE_SECURE": "True",
    "PUBLIC_APP_BASE_URL": "https://spaces.example.org",
    "PLATFORM_STAFF_ORIGINS": "https://spaces.example.org",
    "CSRF_TRUSTED_ORIGINS": "https://spaces.example.org",
    "CORS_ALLOWED_ORIGINS": "https://spaces.example.org",
    "CONTROL_PLANE_PROXY": "false",
}


def _fernet():
    return base64.urlsafe_b64encode(os.urandom(32)).decode()


# The keys scripts/setup-write-environment.sh generates on a fresh install.
PRODUCTION.update({name: _fernet() for name in (
    "API_CLIENT_ENC_KEY", "AUDIT_MAC_MASTER_KEY", "PII_MASTER_KEY", "PII_SEARCH_HASH_KEY", "ACCOUNT_PII_MASTER_KEY")})
PRODUCTION.update({"PUSH_TOKEN_HMAC_KEY": secrets.token_hex(32), "EVENT_STATION_PIN_PEPPER": secrets.token_hex(25),
                   "EVENT_REGISTRATION_CREDENTIAL_DIGEST_KEY": _fernet(),
                   "EVENT_REGISTRATION_CREDENTIAL_KEYS": '{"1":"%s"}' % _fernet(),
                   "EVENT_REGISTRATION_CREDENTIAL_KEY_VERSION": "1"})
# Known, documented warnings: drf-spectacular schema hints (the OpenAPI lane's), and DOT's
# W005 (RFC 9207 iss) and W006 (plaintext token storage, the library behaviour #196 accepted).
ACCEPTED = re.compile(r"\((drf_spectacular\.W001|oauth2_provider\.W00[56])\)")


def _run(extra=()):
    env = {**os.environ, **PRODUCTION}
    return subprocess.run([sys.executable, "manage.py", "check", "--deploy", *extra], cwd=BACKEND, env=env,
                          capture_output=True, text=True, timeout=300)


def test_check_deploy_with_production_settings():
    result = _run()
    strict = _run(("--fail-level", "WARNING"))
    OUT.write_text(f"rc={result.returncode}\n{result.stdout}\n{result.stderr}\n"
                   f"--- fail-level WARNING rc={strict.returncode}\n{strict.stdout}\n{strict.stderr}\n",
                   encoding="utf-8")
    assert result.returncode == 0, result.stdout + result.stderr
    issues = [line for line in (strict.stdout + strict.stderr).splitlines()
              if re.match(r"^\S*: \(\w+\.[EWC]\d+\)", line) and not ACCEPTED.search(line)]
    assert not issues, issues
