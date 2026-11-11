import time

from apps.integrations.mail_providers import chunks
from apps.operations.cloud_jobs import bounded
from apps.operations.cloud_jobs.contracts import BudgetExpired, ChunkContext


def context(checkpoint):
    return ChunkContext(time.monotonic() + 10, lambda: None, checkpoint, "attempt", 1, limit=5)


def test_continuous_early_backlog_cannot_starve_other_surfaces(monkeypatch):
    visited = []
    def phase(name, ctx, cursor):
        visited.append(name)
        return {"processed": 1, "remaining": name == "media", "cursor": cursor + 1 if name == "media" else 0}
    monkeypatch.setattr(chunks, "_phase", phase)
    checkpoint = {}
    for _ in range(12):
        result = chunks.drain_chunk(context(checkpoint))
        assert not result.complete
        checkpoint = result.checkpoint
    assert visited == list(chunks.PHASES) * 3


def test_cooperative_budget_stop_rotates_without_losing_persisted_cursors(monkeypatch):
    def phase(*args):
        raise bounded._StopChunk(BudgetExpired())
    monkeypatch.setattr(chunks, "_phase", phase)
    result = chunks.drain_chunk(context({"phase": 0, "cursors": {"media": 5}}))
    assert not result.complete
    assert result.checkpoint["phase"] == 1
    assert result.checkpoint["cursors"]["media"] == 5
