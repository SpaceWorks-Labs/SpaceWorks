"""Host authority changes occur after rendering and recover exact prior bytes."""

import base64
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
from cloud_setup.host_commit import commit_host_environment


class HostStagingTests(unittest.TestCase):
    def invoke(self, root, *, renderer, fail_write=False):
        environment = ModuleType("apps.backup.cloud_environment")
        private = ModuleType("apps.backup.host_private_file")
        def stage(**kwargs):
            kwargs["compose_renderer"](kwargs["compose_path"], kwargs["static_env_path"], kwargs["pointer_path"])
            for name in ("static_env_path", "pointer_path", "topology_record_path"):
                Path(kwargs[name]).write_bytes(b"proposed")
            return {"status": "staged"}
        def write(path, payload):
            if fail_write and Path(path).name == "database-pointer.env":
                raise OSError("injected")
            Path(path).write_bytes(payload)
        environment.init_from_current_environment = stage
        private.write_private_file_fsynced = write
        private.unlink_private_file_fsynced = lambda path: Path(path).unlink()
        modules = {environment.__name__: environment, private.__name__: private}
        def write_json(path, value):
            Path(path).write_text(json.dumps(value))
        with patch.dict(sys.modules, modules), patch("cloud_setup.host_commit.check_private"), patch("cloud_setup.host_commit.write_json", side_effect=write_json), patch("cloud_setup.host_commit.read_json", side_effect=lambda p: json.loads(Path(p).read_text())):
            return commit_host_environment(ops=root, static_env=root / "cloud.env", compose="compose.yml", renderer=renderer)

    def test_failed_render_never_touches_authority_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def fail(*args):
                raise RuntimeError("render failed")
            with self.assertRaises(RuntimeError):
                self.invoke(root, renderer=fail)
            self.assertFalse((root / "cloud.env").exists())
            self.assertFalse((root / "database-pointer.env").exists())

    def test_failed_commit_removes_only_new_authority_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            unrelated = root / "unrelated"
            unrelated.write_bytes(b"keep")
            with self.assertRaises(OSError):
                self.invoke(root, renderer=lambda *args: "ok", fail_write=True)
            self.assertFalse((root / "cloud.env").exists())
            self.assertEqual(unrelated.read_bytes(), b"keep")
            self.assertEqual(json.loads((root / "cloud-initialization-transaction.json").read_text())["state"], "rolled_back")

    def test_crash_journal_restores_previous_bytes_before_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            targets = [root / name for name in ("cloud.env", "database-pointer.env", "compose-topology.json")]
            for target in targets:
                target.write_bytes(b"partial")
            (root / "cloud-initialization-transaction.json").write_text(json.dumps({"version": 1, "state": "pending", "paths": [str(p.absolute()) for p in targets], "previous": [base64.b64encode(b"prior").decode()] * 3}))
            # Differing initialized configuration is then refused, never reset.
            with self.assertRaises(Exception):
                self.invoke(root, renderer=lambda *args: "ok")
            self.assertTrue(all(p.read_bytes() == b"prior" for p in targets))


if __name__ == "__main__":
    unittest.main()
