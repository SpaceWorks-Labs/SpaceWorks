"""Local-only executable tests; no Django, DB, Docker or network required."""
import importlib.util
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts/installer" / name)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class CapacityRetention(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        (self.root / "backups").mkdir(mode=0o700)
        self.retention = load("retention.py")
        self.receipts = self.retention.receipts

    def backup(self, number):
        path = self.root / "backups" / f"pre-update-20260101T000000Z-{number}.sql.gz"
        path.write_bytes(b"private SQL")
        path.chmod(0o600)
        return path

    def seal(self, path, when=1):
        with patch.object(self.receipts.time, "time", return_value=when):
            self.receipts.seal(self.root, [path], "updated")

    def test_shared_filesystem_allocations_are_added(self):
        capacity = load("capacity.py")
        with self.assertRaises(ValueError):
            capacity.admit([(self.root / "a", 60), (self.root / "b", 60)],
                           disk_usage=lambda _: SimpleNamespace(free=100))
        capacity.admit([(self.root, 50), (self.root / "b", 50)],
                       disk_usage=lambda _: SimpleNamespace(free=100))

    def test_archive_measures_sparse_logical_bytes_and_blocks(self):
        archive = self.root / "archive.tar"
        with tarfile.open(archive, "w") as output:
            member = tarfile.TarInfo("media/clip")
            member.size = 17
            output.addfile(member, io.BytesIO(b"x" * 17))
        self.assertEqual(load("capacity.py").archive_size(archive), 4113)

    def test_archive_rejects_links_and_parent_traversal_before_extraction(self):
        for name, kind in (("../outside", tarfile.REGTYPE), ("link", tarfile.SYMTYPE)):
            archive = self.root / "bad.tar"
            with tarfile.open(archive, "w") as output:
                member = tarfile.TarInfo(name)
                member.type = kind
                member.linkname = "outside"
                output.addfile(member)
            with self.assertRaises(ValueError):
                load("capacity.py").archive_size(archive)

    def test_old_unreceipted_files_are_never_removed(self):
        path = self.backup(1)
        os.utime(path, (1, 1))
        self.retention.expire(self.root, now=100 * 86400)
        self.assertTrue(path.exists())

    def test_fourteen_days_use_completion_not_original_mtime(self):
        old, new = self.backup(1), self.backup(2)
        os.utime(old, (1, 1))
        self.seal(old, when=30 * 86400)
        self.seal(new, when=31 * 86400)
        self.retention.expire(self.root, now=43 * 86400)
        self.assertTrue(old.exists())
        self.retention.expire(self.root, now=45 * 86400)
        self.assertFalse(old.exists())
        self.assertTrue(new.exists())

    def test_newest_recovery_batch_survives_indefinitely(self):
        path = self.backup(1)
        self.seal(path)
        self.retention.expire(self.root, now=365 * 86400)
        self.assertTrue(path.exists())

    def test_changed_receipted_content_is_protected(self):
        old, new = self.backup(1), self.backup(2)
        self.seal(old)
        self.seal(new, 2)
        old.write_text("changed operator recovery bytes")
        self.retention.expire(self.root, now=100 * 86400)
        self.assertTrue(old.exists())

    def test_current_exclusion_and_ambiguous_journal_protect_batches(self):
        old, new = self.backup(1), self.backup(2)
        self.seal(old)
        self.seal(new, 2)
        self.retention.expire(self.root, excluded=[old], now=100 * 86400)
        self.assertTrue(old.exists())
        marker = self.root / ".spaceworks-import-pending.json"
        marker.write_text("ambiguous")
        self.retention.expire(self.root, now=100 * 86400)
        self.assertTrue(old.exists())

    def test_snapshot_tree_with_public_script_modes_has_private_outer_boundary(self):
        config = self.root / "backups/host-config-20260101T000000Z-1"
        config.mkdir(mode=0o700)
        script = config / "script.sh"
        script.write_text("public code, private snapshot")
        script.chmod(0o755)
        self.receipts.seal(self.root, [config], "updated")

    def test_receipt_cannot_name_live_env_or_escape_root(self):
        environment = self.root / ".env"
        environment.write_text("private live key")
        environment.chmod(0o600)
        with self.assertRaises(ValueError):
            self.receipts.seal(self.root, [environment], "updated")

    def test_shorter_retention_is_refused(self):
        with self.assertRaises(ValueError):
            self.retention.expire(self.root, days=13)

    def test_resealing_workspace_cannot_let_old_receipt_delete_newer_recovery(self):
        path = self.backup(1)
        self.seal(path, when=1)
        self.seal(path, when=2)
        self.retention.expire(self.root, now=100 * 86400)
        self.assertTrue(path.exists())
        self.assertEqual(len(list((self.root / ".spaceworks-retention").iterdir())), 1)

    def test_daily_timer_install_is_idempotent_and_removal_is_exact(self):
        schedule = load("retention-schedule.py")
        directory = self.root / "units"
        directory.mkdir()
        calls = []
        invoke = lambda command, **kwargs: calls.append(command)
        name, units = schedule.units(self.root)
        schedule.apply(self.root, directory, "install", run=invoke)
        original = {filename: (directory / filename).read_bytes() for filename in units}
        schedule.apply(self.root, directory, "install", run=invoke)
        self.assertEqual(original, {filename: (directory / filename).read_bytes() for filename in units})
        self.assertIn("OnCalendar=daily", units[name + ".timer"])
        unrelated = directory / "unrelated.timer"
        unrelated.write_text("retain another installation")
        schedule.apply(self.root, directory, "remove", run=invoke)
        self.assertTrue(unrelated.exists())
        self.assertTrue(all(not (directory / filename).exists() for filename in units))
        self.assertIn(["systemctl", "disable", "--now", name + ".timer"], calls)

    def test_modified_daily_timer_is_never_overwritten_or_removed(self):
        schedule = load("retention-schedule.py")
        directory = self.root / "units"
        directory.mkdir()
        name, _ = schedule.units(self.root)
        timer = directory / (name + ".timer")
        timer.write_text("foreign operator-managed unit")
        for action in ("install", "remove"):
            with self.assertRaises(ValueError):
                schedule.apply(self.root, directory, action, run=lambda *a, **k: self.fail("systemctl"))
        self.assertEqual(timer.read_text(), "foreign operator-managed unit")

    def test_systemd_exec_path_escapes_specifiers_and_environment_expansion(self):
        quote = load("retention-schedule.py").quote
        self.assertEqual(quote('/opt/path with $dollar%specifier"quote'), '"/opt/path with $$dollar%%specifier\\"quote"')

    def test_terminal_failed_restore_work_is_bounded_and_unreceipted_work_is_protected(self):
        names = ["restore-" + str(number) * 8 + "-1111-1111-1111-111111111111" for number in (1, 2, 3)]
        paths = [self.root / name for name in names]
        for path in paths:
            path.mkdir(mode=0o700)
            (path / "archive.tar").write_bytes(b"private recovered tar")
            (path / "archive.tar").chmod(0o600)
        with patch.object(self.receipts.time, "time", return_value=1):
            self.receipts.seal(self.root, [paths[0]], "rolled_back")
        with patch.object(self.receipts.time, "time", return_value=2):
            self.receipts.seal(self.root, [paths[1]], "restored")
        self.retention.expire(self.root, now=100 * 86400)
        self.assertFalse(paths[0].exists())
        self.assertTrue(paths[1].exists())
        self.assertTrue(paths[2].exists())

    @unittest.skipIf(os.name == "nt", "POSIX symlink/permission drill")
    def test_receipted_symlink_and_world_readable_material_are_refused(self):
        path = self.backup(1)
        path.chmod(0o644)
        with self.assertRaises(ValueError):
            self.seal(path)
        path.unlink()
        path.symlink_to(self.root / "outside")
        with self.assertRaises(ValueError):
            self.seal(path)


if __name__ == "__main__":
    unittest.main()
