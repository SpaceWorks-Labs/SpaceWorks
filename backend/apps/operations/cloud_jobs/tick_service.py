"""Free-profile scheduler: fair, synchronous, bounded, durable, fail closed."""
from datetime import datetime, timezone
import logging
import time

from django.utils import timezone as clock

from .catalog import periodic_catalog
from .contracts import BudgetExpired, ChunkContext, ChunkResult, GuardLost, JobsUnavailable, admit, chunk_for
from . import journal
from .tick_locks import task_guard
from .tick_policy import database_deadline, free_profile, integer_setting, tick_budget
from .outcomes import TaskReportedFailure

logger = logging.getLogger(__name__)


def fair_order(tasks, states):
    """Reserve alternating turns for critical outbox/reminder work and other work.

    Oldest attempted first prevents a perpetually incomplete first page monopolizing
    ticks. Null attempt timestamps sort first within each lane.
    """
    epoch = datetime.min.replace(tzinfo=timezone.utc)
    ordered = sorted(tasks, key=lambda t: (states[t.key].last_attempt_at or epoch, t.key))
    critical = [t for t in ordered if t.critical]
    other = [t for t in ordered if not t.critical]
    result = []
    for index in range(max(len(critical), len(other))):
        if index < len(critical):
            result.append(critical[index])
        if index < len(other):
            result.append(other[index])
    return result


def _attempt(task, deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return "deferred", "budget_exhausted"
    with task_guard(task.key, remaining) as guard:
        if guard is None:
            return "deferred", "task_busy"
        row, code = journal.claim(task, guard)
        if row is None:
            return ("failed" if code == "operator_reconciliation_required" else "deferred"), code
        if task.free_policy == "disabled_in_free_profile":
            journal.finish(row, task, status="disabled", code=task.free_policy, guard=guard)
            return "deferred", task.free_policy
        callback = chunk_for(task.key)
        if callback is None:
            journal.finish(row, task, status="deferred", code="bounded_adapter_unavailable", guard=guard)
            return "failed", "bounded_adapter_unavailable"
        context = ChunkContext(deadline, lambda: _fence(row, guard), row.checkpoint, row.token, row.generation)
        try:
            from .deadline import total_deadline
            with total_deadline(deadline):
                context.check()
                result = callback(context)
                context.check()
            if not isinstance(result, ChunkResult):
                raise TypeError("Invalid bounded chunk result")
        except GuardLost:
            # Durable uncertain fence survives connection loss. A contender may
            # acquire the advisory lock but cannot execute this task again.
            journal.finish(row, task, status="uncertain", code=GuardLost.code)
            return "failed", GuardLost.code
        except BudgetExpired:
            # Domain checkpoints must already be committed. No blanket success.
            journal.finish(row, task, status="deferred", code="budget_exhausted", guard=guard)
            return "deferred", "budget_exhausted"
        except TaskReportedFailure:
            journal.finish(row, task, status="failed", code="domain_job_failed", guard=guard)
            return "failed", "domain_job_failed"
        except Exception:
            # The callback may have reached a provider: retain the uncertain fence.
            journal.finish(row, task, status="uncertain", code="chunk_failed_reconciliation_required")
            return "failed", "chunk_failed_reconciliation_required"
        status = "completed" if result.complete else "deferred"
        journal.finish(row, task, status=status, checkpoint=result.checkpoint, guard=guard)
        return status, "" if result.complete else "checkpoint_pending"


def _fence(row, guard):
    admit()  # Uncached admission/generation check immediately before every effect.
    journal.check_token(row, guard)


def run_tick():
    if not free_profile():
        raise JobsUnavailable("free_profile_required")
    started = time.monotonic()
    budget = tick_budget()
    admit()
    payload = {"run_id": "", "elapsed_seconds": 0, "completed": 0, "deferred": 0, "failed": 0, "reasons": {}}
    with database_deadline(started + budget):
        run = journal.start_tick()
        payload["run_id"] = str(run.pk)
        tasks = periodic_catalog()
        states = journal.prepare(tasks)
        deadline = started + budget - 2  # DB checkpoint/audit/response headroom
        heavy_started = False
        for task in fair_order(tasks, states):
            if states[task.key].next_due_at and states[task.key].next_due_at > clock.now():
                continue
            if task.heavy and heavy_started:
                outcome, code = "deferred", "heavy_chunk_limit"
            elif time.monotonic() >= deadline:
                outcome, code = "deferred", "budget_exhausted"
            else:
                heavy_started = heavy_started or task.heavy
                try:
                    outcome, code = _attempt(task, deadline)
                except Exception:
                    outcome, code = "failed", "coordination_unavailable"
            payload[outcome] += 1
            if code:
                payload["reasons"][code] = payload["reasons"].get(code, 0) + 1
            logger.info("cloud_tick_task", extra={
                "tick_id": str(run.pk), "task_key": task.key, "outcome": outcome,
                "failure_code": code, "elapsed_seconds": round(time.monotonic() - started, 3),
            })
        payload["elapsed_seconds"] = round(time.monotonic() - started, 3)
        journal.finish_tick(run, payload, bool(payload["failed"]))
        if time.monotonic() < started + budget - 1:
            journal.prune_tick_history(days=integer_setting("FREE_TICK_DETAIL_RETENTION_DAYS", 30, 1, 365))
    return payload, 503 if payload["failed"] else 200
