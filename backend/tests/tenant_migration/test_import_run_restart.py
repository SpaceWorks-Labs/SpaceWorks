"""A killed brokerless materializer can restart before or after journaling bytes."""

from contextlib import nullcontext
from unittest.mock import Mock

import pytest

from apps.tenant_migration import materialization, materialization_failure, object_import, object_storage
from apps.tenant_migration import services_import_run as runner
from apps.tenant_migration.models import TenantImportJob
from apps.tenant_migration.services_import_job import claim_import_job, run_import_job
from tests.data_export.portable_helpers import make_space, make_user
from tests.encryption.conftest import enabled_encryption
from tests.tenant_migration.materialization_helpers import portable_import_case
from tests.tenant_migration.object_helpers import (
    WorkerExit, encryption_key, memory_objects, prepare_source_objects,
    remove_source_object_footprint, write_object_bundle,
)
from tests.tenant_migration.protocol_helpers import superadmin
from tests.tenant_migration.test_import_run_fencing import terminate_lock_backend

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("checkpoint", ["before_journal", "after_journal"])
def test_sequential_restart_reuses_prepared_objects_and_completes(
    checkpoint, memory_objects, monkeypatch,
):
    with enabled_encryption():
        user = make_user(f"restart-{checkpoint}")
        space = make_space(f"restart-{checkpoint}")
        actor = superadmin(f"restart-{checkpoint}")
        with portable_import_case(space, user, prepare_source=prepare_source_objects) as case:
            case.decide_walk_in(user)
            write_object_bundle(case.root)
            remove_source_object_footprint(case, memory_objects)
            case.release_non_regenerable_identities()
            claim_import_job(actor=actor, job=case.job, target_identity={"slug": "restart-target"})
            monkeypatch.setattr("apps.tenant_migration.import_staging.decrypted_archive",
                                lambda _path: nullcontext((case.root, case.carried)))
            real_prepare = materialization.prepare_import_objects

            def interrupt(archive, job):
                if checkpoint == "after_journal":
                    real_prepare(archive, job)
                raise WorkerExit("cron process died during preparation")

            with monkeypatch.context() as first_attempt:
                first_attempt.setattr(materialization, "prepare_import_objects", interrupt)
                with pytest.raises(WorkerExit, match="cron process died"):
                    run_import_job(case.job.pk, actor_id=actor.pk)
            case.job.refresh_from_db()
            assert case.job.status == "materializing"
            assert case.job.target_makerspace_id is None
            first_token = case.job.run_attempt
            assert first_token is not None
            journal_keys = dict(case.job.import_objects.values_list("source_key", "target_key"))
            assert len(journal_keys) == (2 if checkpoint == "after_journal" else 0)
            upload = Mock(wraps=object_storage.upload_staged)
            monkeypatch.setattr(object_storage, "upload_staged", upload)

            completed = run_import_job(
                case.job.pk, actor_id=actor.pk, target_identity={"slug": "restart-target"},
            )

            assert completed.status == TenantImportJob.Status.COMPLETED
            assert completed.run_attempt != first_token
            assert completed.target_makerspace.slug == "restart-target"
            assert completed.import_objects.count() == 2
            assert set(completed.import_objects.values_list("state", flat=True)) == {"verified"}
            assert upload.call_count == (0 if checkpoint == "after_journal" else 2)
            if journal_keys:
                assert dict(completed.import_objects.values_list("source_key", "target_key")) == journal_keys


@pytest.mark.parametrize("checkpoint", ["before_claim", "during_preparation"])
def test_replacement_completes_and_stale_attempt_cannot_change_it(
    checkpoint, memory_objects, monkeypatch,
):
    with enabled_encryption():
        user = make_user(f"takeover-{checkpoint}")
        space = make_space(f"takeover-{checkpoint}")
        actor = superadmin(f"takeover-{checkpoint}")
        with portable_import_case(space, user, prepare_source=prepare_source_objects) as case:
            case.decide_walk_in(user)
            write_object_bundle(case.root)
            remove_source_object_footprint(case, memory_objects)
            case.release_non_regenerable_identities()
            claim_import_job(actor=actor, job=case.job)
            monkeypatch.setattr("apps.tenant_migration.import_staging.decrypted_archive",
                                lambda _path: nullcontext((case.root, case.carried)))
            rollback = Mock()
            monkeypatch.setattr(materialization_failure, "rollback_import_objects", rollback)
            monkeypatch.setattr(object_import, "rollback_import_objects", rollback)
            claim, prepare = runner._claim_attempt, materialization.prepare_import_objects
            stale_lock, replacement_result = [], []

            def replace(lock):
                terminate_lock_backend(lock)
                replacement_result.append(run_import_job(case.job.pk, actor_id=actor.pk))
                assert replacement_result[0].status == "completed"

            def interleaved_claim(job_id, lock):
                first = not stale_lock
                if first:
                    stale_lock.append(lock)
                    if checkpoint == "before_claim":
                        replace(lock)
                return claim(job_id, lock)

            def interleaved_prepare(archive, job):
                plan = prepare(archive, job)
                if checkpoint == "during_preparation" and not replacement_result:
                    # Mark entry before nesting B so B's preparation does not
                    # recursively trigger another takeover of A's dead backend.
                    monkeypatch.setattr(materialization, "prepare_import_objects", prepare)
                    replace(stale_lock[0])
                return plan

            monkeypatch.setattr(runner, "_claim_attempt", interleaved_claim)
            monkeypatch.setattr(materialization, "prepare_import_objects", interleaved_prepare)
            result = run_import_job(case.job.pk, actor_id=actor.pk)
            result.refresh_from_db()
            assert len(replacement_result) == 1
            assert result.status == "completed"
            assert result.run_attempt == replacement_result[0].run_attempt
            assert result.target_makerspace_id == replacement_result[0].target_makerspace_id
            assert result.failure_code == ""
            assert result.import_objects.count() == 2
            assert set(result.import_objects.values_list("state", flat=True)) == {"verified"}
            for row in result.import_objects.all():
                assert row.target_key in memory_objects[row.bucket_kind]
            rollback.assert_not_called()
