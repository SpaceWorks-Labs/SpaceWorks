"""Full schedulers must finish the same binding cycle that free ticks checkpoint."""
from contextlib import nullcontext
from unittest.mock import Mock

import pytest

from apps.operations import storage_qualification
from apps.operations.cloud_jobs import maintenance
from apps.operations.cloud_jobs.contracts import BudgetExpired, ChunkResult, JobsUnavailable


@pytest.mark.parametrize("mode", ["host", "managed"])
def test_full_refresh_consumes_real_adapter_continuation(settings, monkeypatch, mode):
    settings.SPACEWORKS_DEPLOYMENT_MODE = mode
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    monkeypatch.setattr("apps.storage_capabilities.runtime.configured_contracts", lambda: {
        "private": object(), "public_image": object(), "anchor": object(),
    })
    monkeypatch.setattr("apps.operations.cloud_runtime.writer", lambda *args: nullcontext())
    verified, contexts = [], []
    monkeypatch.setattr(storage_qualification, "verify_bindings", lambda **kwargs: verified.extend(kwargs["roles"]))
    monkeypatch.setattr(maintenance, "admit", lambda: None)

    def callback(context):
        contexts.append(context)
        return storage_qualification.refresh_chunk(context)

    monkeypatch.setattr(maintenance, "chunk_for", lambda key: callback)
    assert maintenance.refresh_storage.run() == {"processed": 3, "remaining": False}
    assert verified == ["anchor", "private", "public_image"]
    assert [ctx.checkpoint for ctx in contexts] == [{}, {"position": 1}, {"position": 2}]
    assert len({ctx.deadline for ctx in contexts}) == len({ctx.attempt_id for ctx in contexts}) == 1


def test_refresh_never_spins_on_a_broken_continuation(monkeypatch):
    monkeypatch.setattr(maintenance, "admit", lambda: None)
    callback = Mock(return_value=ChunkResult(False, {}, 0))
    monkeypatch.setattr(maintenance, "chunk_for", lambda key: callback)
    with pytest.raises(JobsUnavailable, match="no_progress"):
        maintenance.refresh_storage.run()
    callback.assert_called_once()


def test_refresh_stops_at_original_deadline(monkeypatch):
    monkeypatch.setattr(maintenance, "admit", lambda: None)
    clock = Mock(return_value=0)
    monkeypatch.setattr(maintenance.time, "monotonic", clock)

    def callback(context):
        clock.return_value = 46
        return ChunkResult(False, {"position": 1}, 1)

    callback = Mock(side_effect=callback)
    monkeypatch.setattr(maintenance, "chunk_for", lambda key: callback)
    with pytest.raises(BudgetExpired):
        maintenance.refresh_storage.run()
    callback.assert_called_once()


def test_refresh_failure_is_never_reported_as_success(monkeypatch):
    monkeypatch.setattr(maintenance, "admit", lambda: None)
    callback = Mock(side_effect=RuntimeError("provider failed"))
    monkeypatch.setattr(maintenance, "chunk_for", lambda key: callback)
    with pytest.raises(RuntimeError, match="provider failed"):
        maintenance.refresh_storage.run()
