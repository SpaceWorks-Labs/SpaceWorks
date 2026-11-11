"""Local-only shell contracts: continuity, privileged targeting and early crash fences."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]
BASH = "C:/Program Files/Git/bin/bash.exe" if os.name == "nt" else shutil.which("bash")
SETTINGS = ("ACCOUNT_SAVED_DETAILS_ENABLED", "ACCOUNT_PII_KEY_BROKER", "ACCOUNT_PII_MASTER_KEY",
            "ACCOUNT_PII_MASTER_KEY_PREVIOUS", "ACCOUNT_PII_AWS_KMS_KEY_ID", "ACCOUNT_SAVED_ASSET_BUDGET_BYTES",
            "ACCOUNT_SAVED_RESUME_SCAN_REQUIRED", "ACCOUNT_SAVED_RESUME_SCANNER",
            "EVENT_REGISTRATION_CREDENTIAL_KEY_VERSION", "EVENT_REGISTRATION_CREDENTIAL_KEYS",
            "EVENT_REGISTRATION_CREDENTIAL_DIGEST_KEY")


@unittest.skipUnless(BASH, "Bash unavailable")
class InstallerInterfaces(unittest.TestCase):
    def invoke(self, code, root, **environment):
        return subprocess.run([BASH, "-c", "set -euo pipefail\n" + code],
                              env={**os.environ, "REPO": ROOT.as_posix(), "ROOT": root.as_posix(), **environment},
                              capture_output=True, text=True, timeout=15)

    def test_all_eleven_settings_forward_once_without_output_or_key_generation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            env_file = root / ".env"
            original = "ACCOUNT_PII_MASTER_KEY='retained-existing-key'\nFREE_TICK_SECRET='retained-trigger'\n"
            env_file.write_text(original)
            values = {name: "private-test-material" for name in SETTINGS}
            values.update(SPACEWORKS_DEPLOYMENT_PROFILE="full", FREE_TICK_SECRET="replacement-refused",
                          FREE_EMAIL_DAILY_CAP="100", EVENT_REGISTRATION_CREDENTIAL_KEYS='{"1":"abc$def"}')
            code = '''
deployment_value() { :; }
source "$REPO/scripts/setup-write-environment.sh"
source "$REPO/scripts/installer/environment-continuity.sh"
forward_installer_environment
forward_installer_environment
[[ ! -v ACCOUNT_PII_MASTER_KEY && ! -v FREE_TICK_SECRET ]]
'''
            result = self.invoke(code, root, **values)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "")
            content = env_file.read_text()
            self.assertTrue(content.startswith(original))
            self.assertNotIn("replacement-refused", content)
            self.assertNotIn("private-test-material", result.stdout + result.stderr)
            for name in SETTINGS:
                self.assertEqual(sum(line.startswith(name + "=") for line in content.splitlines()), 1)
            self.assertIn('EVENT_REGISTRATION_CREDENTIAL_KEYS=\'{"1":"abc$def"}\'', content)
            self.assertIn("FREE_EMAIL_DAILY_CAP='100'", content)

    def test_unset_new_keys_are_never_generated(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / ".env").write_text("SECRET_KEY='existing'\n")
            result = self.invoke('''
deployment_value() { :; }
source "$REPO/scripts/setup-write-environment.sh"
source "$REPO/scripts/installer/environment-continuity.sh"
forward_installer_environment
''', root, SPACEWORKS_DEPLOYMENT_PROFILE="full")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("ACCOUNT_PII_MASTER_KEY=", (root / ".env").read_text())
            self.assertNotIn("EVENT_REGISTRATION_CREDENTIAL_KEYS=", (root / ".env").read_text())

    def test_free_profile_and_newline_injection_refuse_without_printing_material(self):
        for values in ({"SPACEWORKS_DEPLOYMENT_PROFILE": "free"},
                       {"ACCOUNT_PII_MASTER_KEY": "private\nINJECTED=bad"}):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / ".env").write_text("SECRET_KEY='existing'\n")
                result = self.invoke('''
deployment_value() { :; }
source "$REPO/scripts/setup-write-environment.sh"
source "$REPO/scripts/installer/environment-continuity.sh"
forward_installer_environment
''', root, **values)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("INJECTED", (root / ".env").read_text() + result.stdout + result.stderr)

    def test_sudo_forwarding_exports_names_without_secret_argv(self):
        result = self.invoke('''
source "$REPO/scripts/installer/environment-continuity.sh"
preserve_installer_environment
[[ ",$INSTALLER_PRESERVED_NAMES," == *,ACCOUNT_PII_MASTER_KEY,* ]]
[[ "$INSTALLER_PRESERVED_NAMES" != *private-material* ]]
bash -c '[[ "$ACCOUNT_PII_MASTER_KEY" == private-material ]]'
''', ROOT, ACCOUNT_PII_MASTER_KEY="private-material")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("private-material", result.stdout)

    def test_privileged_target_is_marker_bound_identity_not_original_postgres_db(self):
        valid = "sibling_live|12345|11111111-2222-3333-4444-555555555555"
        for proof, accepted in ((valid, True), (valid + "|extra", False),
                                 ("sibling_live|0|bad", False), ("../postgres|1|bad", False)):
            result = self.invoke('''
compose() { printf '%s' "$PROOF"; }
COMPOSE=(compose); APP_SERVICE=backend
source "$REPO/scripts/installer/privileged-target.sh"
admit_privileged_target "$REPO/scripts"
[[ "$SPACEWORKS_PRIVILEGED_TARGET_NAME" == sibling_live ]]
[[ "$SPACEWORKS_PRIVILEGED_TARGET_REQUIRED" == 1 ]]
[[ "$POSTGRES_DB" == original_bootstrap ]]
''', ROOT, PROOF=proof, POSTGRES_DB="original_bootstrap")
            self.assertEqual(result.returncode == 0, accepted, result.stderr)

    def test_interrupted_pre_h1_stops_before_docker_or_backup_effects(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / ".spaceworks-transition.json").write_text('{"phase":"backed-up"}')
            result = self.invoke('''
die() { exit 88; }
docker() { exit 99; }
source "$REPO/scripts/installer/pre-h1.sh"
transition_pre_h1
''', root)
            self.assertEqual(result.returncode, 88)
            self.assertFalse((root / "backups").exists())


if __name__ == "__main__":
    unittest.main()
