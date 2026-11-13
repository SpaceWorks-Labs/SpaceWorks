"""C-26 emergency re-key: a new DEK for writes at once, background re-encrypt, managers told,
archives still readable through their own wrapped copies."""

import pytest

from apps.audit.models import AuditLog
from apps.encryption.models import KeyRotationJob, MakerspaceEncryptionKey
from apps.encryption.rekey_tasks import MAX_ATTEMPTS, advance_running
from apps.encryption.rotation import start_dek_rotation
from apps.notifications.models import Notification
from tests.encryption.conftest import enabled_encryption
from tests.encryption.test_key_rotation import _run_to_completion, _space_with_requests, _superadmin, _versions

pytestmark = pytest.mark.django_db


def test_emergency_rekey_switches_writes_now_and_tells_the_managers():
    with enabled_encryption():
        space, rows = _space_with_requests(2)
        job = start_dek_rotation(_superadmin(), space, emergency=True)
        assert job.kind == KeyRotationJob.Kind.EMERGENCY_REKEY
        assert MakerspaceEncryptionKey.objects.get(makerspace=space, status="active").version == 2
        assert Notification.objects.filter(makerspace=space, event="encryption.emergency_rekey_started").exists()
        _run_to_completion()
        assert all(_versions(row) == {2} for row in rows)
        assert Notification.objects.filter(makerspace=space, event="encryption.emergency_rekey_completed").exists()
        assert AuditLog.objects.filter(makerspace=space, action="encryption.emergency_rekey_completed").exists()


def test_archives_keep_the_old_wrapped_dek_so_old_envelopes_still_open():
    """A retired version is DISABLED, not erased: the wrapped bytes an archive copied still unwrap."""
    from apps.backup.dek_rewrap import enumerate_staged_deks
    from apps.encryption.brokers.local import LocalMasterKeyBroker
    with enabled_encryption():
        space, _rows = _space_with_requests(1)
        archived = {row.version: row for row in enumerate_staged_deks(space.pk)}  # what an archive captures
        start_dek_rotation(_superadmin(), space, emergency=True)
        _run_to_completion()
        assert MakerspaceEncryptionKey.objects.get(makerspace=space, version=1).status == "disabled"
        live = MakerspaceEncryptionKey.objects.get(makerspace=space, version=1)
        assert bytes(live.wrapped_dek) == archived[1].wrapped_dek
        assert LocalMasterKeyBroker().unwrap_dek(archived[1].wrapped_dek, space.pk, 1)


def test_a_failing_chunk_is_retried_then_marked_failed_with_the_new_key_kept(monkeypatch):
    with enabled_encryption():
        space, _rows = _space_with_requests(1)
        job = start_dek_rotation(_superadmin(), space, emergency=True)
        from apps.encryption import rekey_tasks

        def broken(*args, **kwargs):
            raise RuntimeError("chunk failed")
        monkeypatch.setattr(rekey_tasks, "reencrypt_rows", broken)
        for _ in range(MAX_ATTEMPTS):
            advance_running()
        job.refresh_from_db()
        assert job.status == "failed" and job.attempts == MAX_ATTEMPTS and job.error_code == "RuntimeError"
        assert MakerspaceEncryptionKey.objects.get(makerspace=space, status="active").version == 2
        assert AuditLog.objects.filter(makerspace=space, action="encryption.key_job_failed").exists()
        assert Notification.objects.filter(makerspace=space, event="encryption.emergency_rekey_failed").exists()


def test_the_worker_skips_a_frozen_space_and_resumes_later(monkeypatch):
    with enabled_encryption():
        space, _rows = _space_with_requests(1)
        job = start_dek_rotation(_superadmin(), space)
        from contextlib import contextmanager
        from apps.tenant_migration import gate_runtime

        @contextmanager
        def frozen(makerspace_id, *, operation, counts):
            yield False
        monkeypatch.setattr(gate_runtime, "fanout_tenant_write", frozen)
        advance_running()
        job.refresh_from_db()
        assert job.status == "running" and job.rows_done == 0 and job.attempts == 0
