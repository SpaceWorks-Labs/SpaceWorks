"""Private input guarantees and explicit Windows fail-closed behavior."""

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
from cloud_setup.errors import SetupError
from cloud_setup.private_files import check_private, read_json, setup_lock, write_json


class PrivateStateTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Windows-specific check")
    def test_windows_chmod_is_not_claimed_to_enforce_private_acl(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "answers.json"
            path.write_text("{}")
            with self.assertRaises(SetupError) as raised:
                check_private(path)
            self.assertEqual(raised.exception.code, "posix_permissions_required")

    @unittest.skipUnless(os.name == "posix", "Needs actual POSIX file permissions")
    def test_mode_owner_duplicate_json_and_concurrent_invocation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.chmod(0o700)
            path = root / "answers.json"
            write_json(path, {"version": 1})
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(read_json(path), {"version": 1})
            path.write_text('{"version":1,"version":2}')
            with self.assertRaises(SetupError):
                read_json(path)
            path.chmod(0o644)
            with self.assertRaises(SetupError):
                read_json(path)
            with setup_lock(root), self.assertRaises(SetupError):
                with setup_lock(root):
                    pass
            self.assertFalse((root / "setup.lock").exists())


if __name__ == "__main__":
    unittest.main()
