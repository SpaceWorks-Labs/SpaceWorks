"""Local staged imports are retired after commit, never after rollback."""
import pytest
from django.db import transaction

from apps.tenant_migration.archive_retention import schedule_import_archive_unlink

pytestmark = pytest.mark.django_db


def artifacts(tmp_path):
    files = [tmp_path / ("tenant.age" + suffix) for suffix in ["", ".rows.age", ".rows.age.part"]]
    for path in files:
        path.write_bytes(b"encrypted")
    return files


def test_retirement_waits_for_commit_and_replay_accepts_missing_files(tmp_path, django_capture_on_commit_callbacks):
    files = artifacts(tmp_path)
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        schedule_import_archive_unlink(str(files[0]), "cx6-import")
        assert [path.exists() for path in files] == [True, True, True]
    assert len(callbacks) == 1
    assert [path.exists() for path in files] == [False, False, False]
    with django_capture_on_commit_callbacks(execute=True):
        schedule_import_archive_unlink(str(files[0]), "cx6-import")
    assert [path.exists() for path in files] == [False, False, False]


def test_rollback_retains_every_staged_artifact(tmp_path, django_capture_on_commit_callbacks):
    files = artifacts(tmp_path)
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        with pytest.raises(ValueError, match="abort"):
            with transaction.atomic():
                schedule_import_archive_unlink(str(files[0]), "cx6-import")
                raise ValueError("abort")
    assert callbacks == []
    assert [path.exists() for path in files] == [True, True, True]


def test_blank_locator_schedules_no_work(django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        assert schedule_import_archive_unlink("", "cx6-import") is None
        assert schedule_import_archive_unlink(None, "cx6-import") is None
    assert callbacks == []


def test_unlink_failure_is_logged_and_does_not_prevent_sidecar_cleanup(tmp_path, django_capture_on_commit_callbacks, caplog):
    main = tmp_path / "tenant.age"
    main.mkdir()  # A directory cannot be unlinked as a regular archive file.
    sidecars = [tmp_path / ("tenant.age" + suffix) for suffix in [".rows.age", ".rows.age.part"]]
    for path in sidecars:
        path.write_bytes(b"encrypted")
    with django_capture_on_commit_callbacks(execute=True):
        schedule_import_archive_unlink(str(main), "cx6-retention-error")
    assert main.is_dir()
    assert [path.exists() for path in sidecars] == [False, False]
    errors = [record for record in caplog.records if record.message == "tenant_import_archive_unlink_failed"]
    assert len(errors) == 1
    assert (errors[0].job_id, errors[0].archive_path) == ("cx6-retention-error", str(main))
