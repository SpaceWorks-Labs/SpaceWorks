"""Real PostgreSQL lock retention, attempt fencing, and object-journal races."""

from contextlib import contextmanager, nullcontext
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from django.db import connection

from apps.tenant_migration import materialization, materialization_failure, object_import
from apps.tenant_migration import services_import_run as runner
from apps.tenant_migration.import_run_lock import import_run_lock
from apps.tenant_migration.insertion_errors import ImportVerificationError, MaterializationSuperseded
from apps.tenant_migration.models import TenantImportJob, TenantImportObject
from apps.tenant_migration.object_export import object_member_path
from tests.data_export.portable_helpers import make_space, make_user
from tests.encryption.conftest import enabled_encryption
from tests.tenant_migration.materialization_helpers import portable_import_case
from tests.tenant_migration.test_import_async_staging import (
    actor, ops_dir, pending_job, portable_tree,
)

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def materializing_job(pending_job):
    return pending_job(status=TenantImportJob.Status.MATERIALIZING)


def terminate_lock_backend(lock):
    # The dedicated lock connection differs from Django's application connection.
    # Wait for termination so replacement acquisition has no timing/sleep race.
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_backend_pid()")
        assert cursor.fetchone()[0] != lock.backend_pid
        cursor.execute("SELECT pg_terminate_backend(%s, 5000)", [lock.backend_pid])
        assert cursor.fetchone()[0] is True


def test_held_lock_makes_second_run_return_without_status_or_object_changes(
    actor, materializing_job, monkeypatch,
):
    job = materializing_job
    execute, rollback = Mock(), Mock()
    monkeypatch.setattr(runner, "_execute", execute)
    monkeypatch.setattr(object_import, "rollback_import_objects", rollback)
    with import_run_lock(job.pk) as first:
        assert first.acquired and first.retained()
        with first.lock_connection.cursor() as cursor:
            cursor.execute("SHOW idle_in_transaction_session_timeout")
            assert cursor.fetchone()[0] == "0"
        result = runner.run_import_job(job.pk, actor_id=actor.pk)
        assert result.status == "materializing"
        assert result.run_attempt is None
        assert first.retained()
    execute.assert_not_called()
    rollback.assert_not_called()
    job.refresh_from_db()
    assert job.status == "materializing"
    assert job.run_attempt is None
    assert not job.import_objects.exists()
    with import_run_lock(job.pk) as next_attempt:
        assert next_attempt.acquired


@pytest.mark.parametrize("fails", [False, True])
def test_execution_releases_lock_on_success_and_exception(
    actor, materializing_job, monkeypatch, fails,
):
    job = materializing_job
    execute = Mock(return_value=job, side_effect=RuntimeError("attempt interrupted") if fails else None)
    monkeypatch.setattr(runner, "_execute", execute)
    if fails:
        with pytest.raises(RuntimeError, match="attempt interrupted"):
            runner.run_import_job(job.pk, actor_id=actor.pk)
    else:
        runner.run_import_job(job.pk, actor_id=actor.pk)
    job.refresh_from_db()
    assert job.run_attempt is not None
    execute.assert_called_once()
    with import_run_lock(job.pk) as next_attempt:
        assert next_attempt.acquired and next_attempt.retained()


def test_claim_with_dead_lock_cannot_overwrite_replacement_token(materializing_job):
    job = materializing_job
    with import_run_lock(job.pk) as stale:
        assert stale.acquired
        terminate_lock_backend(stale)
        with import_run_lock(job.pk) as replacement:
            assert replacement.acquired
            winning_token = runner._claim_attempt(job.pk, replacement)
            assert winning_token is not None
            assert runner._claim_attempt(job.pk, stale) is None
            job.refresh_from_db()
            assert job.run_attempt == winning_token
            assert job.status == "materializing"
            assert replacement.retained()


def test_lock_lost_before_claim_does_not_execute_fail_or_cleanup(
    actor, materializing_job, monkeypatch,
):
    job = materializing_job
    execute, rollback = Mock(), Mock()

    @contextmanager
    def lose_before_claim(job_id):
        with import_run_lock(job_id) as stale:
            assert stale.acquired
            terminate_lock_backend(stale)
            yield stale

    monkeypatch.setattr(runner, "import_run_lock", lose_before_claim)
    monkeypatch.setattr(runner, "_execute", execute)
    monkeypatch.setattr(object_import, "rollback_import_objects", rollback)
    result = runner.run_import_job(job.pk, actor_id=actor.pk)
    assert result.status == "materializing"
    assert result.run_attempt is None
    assert result.failure_code == ""
    assert result.terminal_at is None
    execute.assert_not_called()
    rollback.assert_not_called()


def test_materialization_refuses_superseded_token_before_creating_target(
    materializing_job, portable_tree, monkeypatch,
):
    job = materializing_job
    stale, winning = uuid4(), uuid4()
    TenantImportJob.objects.filter(pk=job.pk).update(run_attempt=winning)
    rollback, create_target = Mock(), Mock()
    monkeypatch.setattr(materialization_failure, "rollback_import_objects", rollback)
    monkeypatch.setattr(materialization, "create_target_makerspace", create_target)
    with pytest.raises(MaterializationSuperseded) as raised:
        materialization.materialize_tenant(portable_tree.root, job, (), run_attempt=stale)
    assert "replacement" in str(raised.value), repr(raised.value.__cause__)
    job.refresh_from_db()
    assert job.status == "materializing"
    assert job.run_attempt == winning
    assert job.target_makerspace_id is None
    rollback.assert_not_called()
    create_target.assert_not_called()


@pytest.mark.parametrize("failure", ["superseded", "generic"])
def test_stale_runner_failure_neither_fails_winner_nor_rolls_back_objects(
    actor, materializing_job, portable_tree, monkeypatch, failure,
):
    job = materializing_job
    winning = uuid4()
    rollback = Mock()
    monkeypatch.setattr(object_import, "rollback_import_objects", rollback)
    monkeypatch.setattr("apps.tenant_migration.import_staging.decrypted_archive",
                        lambda _path: nullcontext((portable_tree.root, ())))

    def replaced(*_args, **kwargs):
        assert kwargs["run_attempt"] is not None
        TenantImportJob.objects.filter(pk=job.pk).update(run_attempt=winning)
        if failure == "superseded":
            raise MaterializationSuperseded("replacement owns the job")
        raise RuntimeError("stale archive I/O failed")

    monkeypatch.setattr(materialization, "materialize_tenant", replaced)
    if failure == "generic":
        with pytest.raises(RuntimeError, match="stale archive I/O"):
            runner.run_import_job(job.pk, actor_id=actor.pk)
    else:
        assert runner.run_import_job(job.pk, actor_id=actor.pk).status == "materializing"
    job.refresh_from_db()
    assert job.status == "materializing"
    assert job.run_attempt == winning
    assert job.failure_code == ""
    assert job.terminal_at is None
    rollback.assert_not_called()


def test_stale_materialization_failure_does_not_cleanup(materializing_job, monkeypatch):
    job, stale, winning = materializing_job, uuid4(), uuid4()
    TenantImportJob.objects.filter(pk=job.pk).update(run_attempt=winning)
    rollback = Mock()
    monkeypatch.setattr(materialization_failure, "rollback_import_objects", rollback)
    with pytest.raises(MaterializationSuperseded):
        materialization_failure.handle_materialization_failure(
            job=job, target=None, error=RuntimeError("stale insert failed"), run_attempt=stale,
        )
    job.refresh_from_db()
    assert job.status == "materializing"
    assert job.run_attempt == winning
    rollback.assert_not_called()


def test_lock_lost_before_commit_rolls_back_materialization_without_cleanup(monkeypatch):
    # Use the complete existing portable fixture: the transaction really creates
    # target rows, and PostgreSQL must roll them back when the lock backend dies.
    with enabled_encryption():
        source_user = make_user("run-lock-loss")
        source = make_space("run-lock-loss")
        with portable_import_case(source, source_user) as case:
            case.decide_walk_in(source_user)
            case.release_non_regenerable_identities()
            TenantImportJob.objects.filter(pk=case.job.pk).update(status="materializing")
            rollback = Mock()
            promote = Mock(side_effect=AssertionError("uncommitted objects cannot be promoted"))
            monkeypatch.setattr(materialization_failure, "rollback_import_objects", rollback)
            monkeypatch.setattr(materialization, "promote_import_objects", promote)
            verify = materialization.verify_materialization
            created_target_ids = []
            with import_run_lock(case.job.pk) as lock:
                assert lock.acquired
                attempt = runner._claim_attempt(case.job.pk, lock)

                def lose_after_verification(**kwargs):
                    verify(**kwargs)
                    created_target_ids.append(kwargs["target"].pk)
                    terminate_lock_backend(lock)

                monkeypatch.setattr(materialization, "verify_materialization", lose_after_verification)
                with pytest.raises(MaterializationSuperseded, match="lock was lost"):
                    materialization.materialize_tenant(
                        case.root, case.job, case.carried, run_attempt=attempt, run_lock=lock,
                    )
            from apps.makerspaces.models import Makerspace

            assert len(created_target_ids) == 1
            assert not Makerspace.objects.filter(pk__in=created_target_ids).exists()
            case.job.refresh_from_db()
            assert case.job.target_makerspace_id is None
            assert case.job.status == "materializing"
            assert case.job.run_attempt == attempt
            rollback.assert_not_called()
            promote.assert_not_called()


@pytest.fixture
def journal_race(materializing_job, tmp_path, monkeypatch):
    data = b"digest-verified carried bytes"
    record = {
        "bucket_kind": "private", "source_key": "evidence/source-photo",
        "size": len(data), "sha256": hashlib.sha256(data).hexdigest(),
        "version_id": None, "content_type": "image/png",
    }
    member = tmp_path / object_member_path("private", record["source_key"])
    member.parent.mkdir(parents=True, exist_ok=True)
    member.write_bytes(data)
    (tmp_path / "objects" / "manifest.jsonl").write_text(json.dumps(record) + "\n", encoding="utf-8")
    monkeypatch.setattr(object_import.object_storage, "choose_target_key",
                        lambda *_args: ("losing-random-key", True))
    monkeypatch.setattr(object_import.object_storage, "digest_object",
                        lambda *_args: (len(data), record["sha256"]))
    return SimpleNamespace(job=materializing_job, archive=SimpleNamespace(root=tmp_path), record=record)


@pytest.mark.parametrize("winning_key", ["winning-random-key", "evidence/source-photo"])
def test_journal_insert_loser_adopts_winner_key_and_regeneration_flag(
    journal_race, monkeypatch, winning_key,
):
    case = journal_race

    def insert_winner(staging_key, _member):
        TenantImportObject.objects.create(
            job=case.job, staging_key=staging_key, target_key=winning_key,
            **{key: value for key, value in case.record.items() if key != "version_id"},
        )

    upload = Mock(side_effect=insert_winner)
    monkeypatch.setattr(object_import.object_storage, "upload_staged", upload)
    plan = object_import.prepare_import_objects(case.archive, case.job)
    source_key = case.record["source_key"]
    assert plan.target_keys == {source_key: winning_key}
    changed = winning_key != source_key
    assert plan.regenerated == int(changed)
    assert plan.regenerated_keys == ({source_key: winning_key} if changed else {})
    assert plan.staged == 1
    assert case.job.import_objects.count() == 1
    assert case.job.import_objects.get().target_key == winning_key
    upload.assert_called_once()


@pytest.mark.parametrize("mismatch", ["sha256", "content_type", "size", "bucket_kind", "state"])
def test_journal_insert_loser_rejects_mismatching_winner(journal_race, monkeypatch, mismatch):
    case = journal_race

    def insert_wrong_winner(staging_key, _member):
        values = {key: value for key, value in case.record.items() if key != "version_id"}
        values[mismatch] = {
            "sha256": "f" * 64, "content_type": "application/pdf",
            "size": 999, "bucket_kind": "public_image", "state": "rolled_back",
        }[mismatch]
        TenantImportObject.objects.create(
            job=case.job, staging_key=staging_key, target_key="winning-key", **values,
        )

    monkeypatch.setattr(object_import.object_storage, "upload_staged", insert_wrong_winner)
    with pytest.raises(ImportVerificationError, match="journal conflicts"):
        object_import.prepare_import_objects(case.archive, case.job)
    assert case.job.import_objects.count() == 1
