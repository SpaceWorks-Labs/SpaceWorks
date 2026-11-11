"""Credential reuse, legacy compatibility and provider config boundaries."""

import base64
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
from cloud_setup.email_config import validate_config
from cloud_setup.errors import SetupError
from cloud_setup.secrets import continuity_probe, ensure_secrets, validate_secrets
from cloud_setup.secret_files import materialize_secret_files, read_config


class SecretEmailTests(unittest.TestCase):
    def test_legacy_long_django_key_and_pepper_are_preserved(self):
        value = {"SECRET_KEY": "legacy-symbols!" * 5, "EVENT_STATION_PIN_PEPPER": "legacy-pepper!" * 4}
        self.assertIs(validate_secrets(value), value)

    def test_malformed_or_reused_wrapping_keys_refused(self):
        same = base64.urlsafe_b64encode(b"x" * 32).decode()
        for value in ({"PII_MASTER_KEY": "bad"}, {"API_CLIENT_ENC_KEY": same, "AUDIT_MAC_MASTER_KEY": same}):
            with self.assertRaises(SetupError):
                validate_secrets(value)

    def test_read_only_validation_refuses_missing_continuity(self):
        with self.assertRaises(SetupError) as raised:
            continuity_probe({}, free=True)
        self.assertEqual(raised.exception.code, "continuity_missing")

    def test_provider_credentials_cannot_supply_api_base_or_backend(self):
        for provider, config in (("resend", {"api_key": "sentinel", "api_url": "https://evil.example"}), ("postmark", {"backend": "untrusted.path"}), ("mailgun", {"api_key": "sentinel", "domain": "mail.example", "region": "bad"})):
            with self.assertRaises(SetupError) as raised:
                validate_config(provider, config)
            self.assertNotIn("sentinel", str(raised.exception))

    def test_ses_has_distinct_typed_identity_fields(self):
        validate_config("ses", {"region": "us-east-1"})
        with self.assertRaises(SetupError):
            validate_config("ses", {"region": "us-east-1", "access_key_id": "only-half"})
        with self.assertRaises(SetupError):
            validate_config("ses", {"region": "https://evil.example"})

    def test_inline_provider_file_is_secret_and_materializes_privately(self):
        from cloud_setup.answers import FORBIDDEN_ENV
        name = "SPACEWORKS_EMAIL_PROVIDER_CONFIG_B64"
        values = {"SPACEWORKS_DEPLOYMENT_MODE": "managed", "SPACEWORKS_SECRET_FILE_MODE": "inline", name: base64.b64encode(b'{"api_key":"sentinel"}').decode(), "EMAIL_PROVIDER_CONFIG_FILE": "/tmp/spaceworks-secrets/email.json"}
        self.assertIsNotNone(FORBIDDEN_ENV.search(name))
        self.assertEqual(read_config(values, "EMAIL_PROVIDER_CONFIG_FILE"), {"api_key": "sentinel"})
        with patch("cloud_setup.secret_files.write_private") as write:
            materialize_secret_files(values)
        self.assertNotIn(name, values)
        self.assertEqual(write.call_args.args[0], Path("/tmp/spaceworks-secrets/email.json"))

    def test_inline_provider_files_cannot_activate_for_host(self):
        values = {"SPACEWORKS_DEPLOYMENT_MODE": "host", "SPACEWORKS_SECRET_FILE_MODE": "inline", "SPACEWORKS_EMAIL_PROVIDER_CONFIG_B64": base64.b64encode(b'{}').decode()}
        with self.assertRaises(SetupError):
            materialize_secret_files(values)

    @unittest.skipUnless(importlib.util.find_spec("cryptography"), "Backend cryptography dependency unavailable locally")
    def test_generation_survives_failure_without_rotating_any_key(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def write(path, value):
                Path(path).write_text(json.dumps(value))
            def read(path):
                return json.loads(Path(path).read_text())
            with patch("cloud_setup.secrets.write_json", side_effect=write), patch("cloud_setup.secrets.read_json", side_effect=read), patch("cloud_setup.secrets.age_identity", side_effect=[SetupError("age_failed", "Retry with same state."), None]):
                with self.assertRaises(SetupError):
                    ensure_secrets(root, {"version": 1, "values": {}}, free=True)
                previous = read(root / "secrets.json")["values"]
                current = ensure_secrets(root, {"version": 1, "values": {}}, free=True)
            self.assertEqual(previous, current)
            self.assertNotEqual(current["PII_MASTER_KEY"], current["PII_SEARCH_HASH_KEY"])
            self.assertNotEqual(current["API_CLIENT_ENC_KEY"], current["AUDIT_MAC_MASTER_KEY"])


if __name__ == "__main__":
    unittest.main()
