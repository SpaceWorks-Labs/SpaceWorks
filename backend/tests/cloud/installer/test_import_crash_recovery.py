"""Actual fsync/rename failure injection in the POSIX continuity journal protocol."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys

ROOT = Path(__file__).resolve().parents[4]


@unittest.skipIf(os.name == "nt", "Requires actual POSIX ownership, directory fsync and private modes")
class ImportCrashRecovery(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.ops = self.root / "ops"
        self.work = self.ops / "work/import-abcdefgh"
        self.work.mkdir(parents=True, mode=0o700)
        self.backup = self.root / ".env.pre-restore-20260101T000000Z-1"
        self.backup.write_bytes(b"SECRET_KEY='retained-original'\n")
        self.backup.chmod(0o600)
        (self.work / "records.json").write_text("{}")
        (self.work / "records.json").chmod(0o600)
        self.journal = self.root / ".spaceworks-import-pending.json"
        spec = importlib.util.spec_from_file_location("journal", ROOT / "scripts/installer/import-journal.py")
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.original = self.backup.read_bytes()

    def action(self, action, *extra):
        with patch.object(sys, "argv", ["journal", action, str(self.root), str(self.ops), *map(str, extra)]):
            self.module.main()

    def begin(self):
        self.action("begin", self.work, self.backup.name, "sha256:" + "a" * 64)

    def test_failure_at_each_begin_fsync_never_changes_environment_or_records(self):
        real = os.fsync
        for fail_at in range(1, 7):
            count = 0
            def fsync(descriptor):
                nonlocal count
                count += 1
                if count == fail_at:
                    raise OSError("injected fsync failure")
                return real(descriptor)
            if self.journal.exists():
                self.journal.unlink()
            with patch.object(self.module.os, "fsync", side_effect=fsync):
                try:
                    self.begin()
                except OSError:
                    pass
            self.assertEqual(self.backup.read_bytes(), self.original)
            self.assertEqual((self.work / "records.json").read_text(), "{}")
            if self.journal.exists():
                self.assertEqual(json.loads(self.journal.read_text())["phase"], "configuration")

    def test_seal_crash_after_atomic_replace_keeps_registration_ambiguous(self):
        self.begin()
        with patch.object(self.module, "sync_parent", side_effect=OSError("crash after replace")):
            with self.assertRaises(OSError):
                self.action("seal")
        self.assertEqual(json.loads(self.journal.read_text())["phase"], "restore_registration")
        with self.assertRaises(SystemExit) as failure:
            self.action("read")
        self.assertIn("Environment-only rollback is refused", str(failure.exception))
        self.assertEqual(self.backup.read_bytes(), self.original)

    def test_failure_before_replace_leaves_configuration_recoverable_and_new_checkpoint_private(self):
        self.begin()
        with patch.object(self.module.os, "replace", side_effect=OSError("crash before replace")):
            with self.assertRaises(OSError):
                self.action("seal")
        self.assertEqual(json.loads(self.journal.read_text())["phase"], "configuration")
        self.assertTrue(self.journal.with_suffix(".new").exists())
        self.action("clear")
        self.assertFalse(self.journal.exists())
        self.assertFalse(self.journal.with_suffix(".new").exists())

    def test_registered_checkpoint_survives_crash_and_never_allows_key_only_rollback(self):
        self.begin()
        self.action("seal")
        restore_id = "11111111-2222-3333-4444-555555555555"
        with patch.object(self.module, "sync_parent", side_effect=OSError("crash after registered")):
            with self.assertRaises(OSError):
                self.action("registered", restore_id)
        self.assertEqual(json.loads(self.journal.read_text())["restore_id"], restore_id)
        with self.assertRaises(SystemExit):
            self.action("read")


if __name__ == "__main__":
    unittest.main()
