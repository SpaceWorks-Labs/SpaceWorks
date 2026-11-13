"""Stdlib harness checks; these can run without Django, Docker or provider access."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

HELPERS = Path(__file__).resolve().parents[4] / "tests" / "deploy"
sys.path.insert(0, str(HELPERS))
if not (HELPERS / "docker.py").exists():  # R3: the repo-root tests/deploy helpers are absent from this checkout
    import pytest
    pytest.skip("tests/deploy verification helpers are not in this checkout", allow_module_level=True)

from docker import Docker
from evidence import Evidence, REQUIRED, validate_facts
from free_environment import read_env
from process import Result, Runner, VerificationError, private_write
from recovery_checks import compare_state, qualify_provider, same_artifact
from scenarios import load_cases
from verify import arguments
import verify as entrypoint
from preflight import check as dependencies


class HarnessTests(unittest.TestCase):
    def test_documented_cli_entrypoints_parse(self):
        cases = [
            ["container", "--fresh", "--upgrade", "--source", "."],
            ["container", "--from-release", "v1.0.0-main.1.abcdef123456", "--to-source", "."],
            ["free", "--source", ".", "--postgres-major", "17"],
            ["vm", "--target", "disposable", "--fresh", "--upgrade", "--disposable-vm-marker", "marker.json"],
        ]
        for argv in cases:
            self.assertEqual(arguments(argv).mode, argv[0])

    def test_an_incomplete_gate_cannot_finish_green(self):
        for mode in REQUIRED:
            with self.subTest(mode=mode), self.assertRaises(VerificationError):
                Evidence(mode, {}).finish()

    def test_missing_lane_interfaces_refuse_before_any_docker_effect(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(VerificationError, "cross_lane_dependencies_missing"):
                dependencies(Path(directory), "free")

    def test_cleanup_failure_changes_a_successful_run_to_nonzero(self):
        def complete(_args, _docker, evidence, _archive, _private):
            for name in REQUIRED["free"]:
                evidence.record(name, observed=True)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory, "evidence")
            with patch.object(entrypoint, "snapshot", return_value={}), \
                    patch.object(entrypoint, "check_dependencies"), \
                    patch.dict(sys.modules, {"free": SimpleNamespace(run=complete)}), \
                    patch.object(Docker, "cleanup", side_effect=VerificationError("cleanup_failed:container")):
                code = entrypoint.main(["free", "--output", str(output)])
            self.assertEqual(code, 1)
            self.assertEqual(json.loads((output / "evidence.json").read_text())["status"], "incomplete")

    def test_custody_cannot_satisfy_either_recovery_gate(self):
        evidence = Evidence("recovery", {})
        evidence.record("archive_custody", custody_only=True)
        with self.assertRaises(VerificationError):
            evidence.finish()

    def test_private_data_never_enters_evidence(self):
        for facts in ({"secret": "redacted"}, {"endpoint": "https://private.test/path"},
                      {"subject": "member@example.test"}, {"object": "signed?token=secret"}):
            with self.subTest(facts=facts), self.assertRaises(VerificationError):
                validate_facts(facts)
        with self.assertRaises(VerificationError):
            validate_facts({"elapsed": float("nan")})

    def test_secret_leak_is_detected_without_echoing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            runner = Runner(directory)
            value = runner.secret("harness-secret-canary-value")
            with self.assertRaisesRegex(VerificationError, "secret_leak"):
                runner.run([sys.executable, "-c", "import sys; print(sys.stdin.read())"],
                           input_bytes=value.encode())
            self.assertNotIn(value, Path(directory, "command-0001.log").read_text())

    def test_private_file_create_refuses_existing_path_and_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "private")
            private_write(path, "first")
            with self.assertRaises(FileExistsError):
                private_write(path, "replacement")
            self.assertEqual(path.read_text(), "first")

    def test_plain_env_has_no_shell_evaluation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "runtime.env")
            path.write_text("KEY=$(do-not-execute)\n", encoding="utf-8")
            self.assertEqual(read_env(path)["KEY"], "$(do-not-execute)")
            path.write_text("KEY=first\nKEY=second\n", encoding="utf-8")
            with self.assertRaises(VerificationError):
                read_env(path)

    def test_cleanup_refuses_a_resource_without_this_runs_label(self):
        class Fake:
            def run(self, argv, **_kwargs):
                if argv[2] == "inspect":
                    return Result(0, b'{"Config":{"Labels":{"org.spaceworks.verification":"other"}}}', 0)
                raise AssertionError("must never remove foreign resource")
        docker = Docker(Fake(), "this-run")
        with self.assertRaisesRegex(VerificationError, "ownership"):
            docker.remove("container", "foreign-id")

    def test_portable_recovery_requires_identical_ciphertext(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = [Path(directory, name) for name in ("export", "retrieve", "import")]
            for path in paths:
                path.write_bytes(b"ciphertext")
            digest = hashlib.sha256(b"ciphertext").hexdigest()
            self.assertTrue(same_artifact(*paths, digest)["same_artifact"])
            paths[-1].write_bytes(b"repacked-ciphertext")
            with self.assertRaises(VerificationError):
                same_artifact(*paths, digest)

    def test_counts_do_not_substitute_for_real_recovery_probe_digests(self):
        with self.assertRaises(VerificationError):
            compare_state({"rows": 1}, {"rows": 1})
        names = ("rows", "references", "objects", "expiry", "immutable", "decrypted", "identity")
        state = {name: {"sample": "a" * 64} for name in names}
        self.assertEqual(compare_state(state, state)["verified_sets"], 7)
        different = {**state, "decrypted": {"sample": "b" * 64}}
        with self.assertRaises(VerificationError):
            compare_state(state, different)

    def test_no_automatic_provider_recovery_pass_for_missing_facility(self):
        receipt = {"target_mode": "managed", "target_offline": True,
                   "source_deployment": "source", "target_deployment": "fresh",
                   "old_credentials_revoked": True, "keys_escrow_verified": True,
                   "provider_backup_available": False}
        with self.assertRaisesRegex(VerificationError, "unavailable"):
            qualify_provider(receipt)
        receipt["provider_backup_available"] = "true"
        with self.assertRaisesRegex(VerificationError, "unavailable"):
            qualify_provider(receipt)

    def test_scenario_manifest_rejects_escape_and_duplicate_cases(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "cases.json")
            payload = {"version": 1, "cases": {"free": [
                {"name": "loan", "script": "../escape.py", "timeout": 30},
            ]}}
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(VerificationError):
                load_cases(path, "free")


if __name__ == "__main__":
    unittest.main()
