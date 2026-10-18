"""One committed day at a time; preserve historical revisions and resume cursor."""
from datetime import datetime, timedelta

from django.utils import timezone

from apps.makerspaces.servability import servable_queryset
from apps.operations.models import ReportRollupCursor
from apps.operations.report_rollups import SOURCE_MODULE, _day_start, _rollup_start, finalize_evidence_rollups
from apps.tenant_migration.gate_runtime import fanout_tenant_write

from .contracts import BudgetExpired, ChunkResult


def chunk(context):
    from apps.makerspaces.models import Makerspace
    checkpoint = dict(context.checkpoint)
    target = datetime.fromisoformat(checkpoint["target"]) if checkpoint.get("target") else _day_start(timezone.now())
    processed = 0
    spaces = servable_queryset(Makerspace.objects.all()).order_by("pk")
    if checkpoint.get("space"):
        spaces = spaces.filter(pk__gte=checkpoint["space"])
    counts = {"skipped": 0}
    try:
        for space in spaces[:context.limit]:
            context.check()
            cursor, _ = ReportRollupCursor.objects.get_or_create(makerspace=space, source_module=SOURCE_MODULE)
            day = (datetime.fromisoformat(checkpoint["day"]) if checkpoint.get("space") == space.pk
                   and checkpoint.get("day") else _rollup_start(space, cursor, target, None))
            with fanout_tenant_write(space.pk, operation="report_rollup", counts=counts) as allowed:
                if allowed:
                    while day < target:
                        checkpoint = {"space": space.pk, "day": day.isoformat(), "target": target.isoformat()}
                        context.check()
                        if processed >= context.limit:
                            return ChunkResult(False, checkpoint, processed)
                        end = min(day + timedelta(days=1), target)
                        finalize_evidence_rollups(space, through=end, start_at=day)
                        day, processed = end, processed + 1
                        checkpoint["day"] = day.isoformat()
            checkpoint = {"space": space.pk + 1, "target": target.isoformat()}
        remains = spaces.filter(pk__gte=checkpoint.get("space", 0)).exists()
        return ChunkResult(not remains, checkpoint if remains else {}, processed)
    except BudgetExpired:
        return ChunkResult(False, checkpoint, processed)
