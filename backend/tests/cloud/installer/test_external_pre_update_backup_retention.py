"""Decision 245(a): the pre-update dump of an OUTSIDE database (`.dump`) is sealed and retained like the
bundled `.sql.gz`. Local-only; no Django, DB, Docker or network required."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[4]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts/installer" / name)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class ExternalPreUpdateBackupName(unittest.TestCase):
    def test_both_dump_kinds_are_owned_recovery_material(self):
        backup = load("retention-receipts.py").BACKUP
        for name in ("pre-update-20261110T101010Z-123.sql.gz", "pre-update-20261110T101010Z-123.dump"):
            self.assertTrue(backup.fullmatch(f"backups/{name}"), name)

    def test_lookalikes_are_not(self):
        backup = load("retention-receipts.py").BACKUP
        for name in ("pre-update-1.dump.evil", "pre-update-1.sql", "other-1.dump", "../pre-update-1.dump"):
            self.assertFalse(backup.fullmatch(f"backups/{name}"), name)

    def test_the_dump_name_the_updater_writes_matches_the_dumper_and_the_receipt(self):
        import re
        dumper = (ROOT / "scripts/installer/external-db-dump.py").read_text(encoding="utf-8")
        self.assertIn(r"pre-update-[0-9TZ]+-[0-9]+\.dump", dumper)
        name = "pre-update-20261110T101010Z-4242.dump"
        self.assertTrue(re.fullmatch(r"pre-update-[0-9TZ]+-[0-9]+\.dump", name))
        self.assertTrue(load("retention-receipts.py").BACKUP.fullmatch(f"backups/{name}"))

    def test_the_copied_dump_is_created_private(self):
        script = (ROOT / "scripts/installer/update-backup.sh").read_text(encoding="utf-8")
        self.assertIn("umask 077", script.split("create_external_update_backup()")[1])


if __name__ == "__main__":
    unittest.main()
