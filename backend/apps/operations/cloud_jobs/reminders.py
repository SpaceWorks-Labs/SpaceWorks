"""Resume one reminder source at a time, reserving room for committed dispatch."""
from dataclasses import replace

from django.utils import timezone

from . import bounded
from .contracts import BudgetExpired, ChunkResult


def chunk(context):
    from apps.operations.reminder_registry import registered_sources
    from apps.operations.reminder_sweeper import run_reminder_sweep
    from apps.integrations.broadcasts_worker import resume_broadcasts
    from apps.notifications.retention import run_notification_retention
    sources = registered_sources()
    phases = ["retention", "broadcasts", *(source.key for source in sources)]
    states = dict(context.checkpoint.get("states", {}))
    done = set(context.checkpoint.get("done", []))
    index = int(context.checkpoint.get("next", 0)) % len(phases)
    processed = 0
    start = index
    try:
        for offset in range(len(phases)):
            position = (start + offset) % len(phases)
            phase = phases[position]
            if phase in done:
                continue
            context.check()
            if processed >= context.limit:
                break
            inner = replace(context, checkpoint=states.get(phase, {}), limit=context.limit - processed)
            if phase == "retention":
                callback = lambda: run_notification_retention(now=timezone.now(), limit=3)
            elif phase == "broadcasts":
                callback = resume_broadcasts
            else:
                # Reserve turns for committed dispatch after subject discovery.
                callback = lambda: run_reminder_sweep(limit=3, source_keys=(phase,))
            result = bounded.invoke(inner, callback)
            processed += result.processed
            if result.complete:
                done.add(phase)
                states.pop(phase, None)
            else:
                states[phase] = result.checkpoint
            index = (position + 1) % len(phases)
    except BudgetExpired:
        pass
    complete = set(phases) <= done
    return ChunkResult(complete, {} if complete else {"next": index, "states": states, "done": sorted(done)}, processed)
