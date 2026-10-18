"""Daily tenant fan-out: the availability module owns the observation itself."""

import logging

from django.utils import timezone

from apps.accounts import rbac
from apps.makerspaces.models import Makerspace
from apps.makerspaces.servability import servable_queryset
from apps.tenant_migration.gate_runtime import fanout_tenant_write

logger = logging.getLogger(__name__)


def snapshot_inventory_stock(*, now=None):
    from .availability_stock import observe_stock

    now = now or timezone.now()
    counts = {"created": 0, "skipped": 0, "failed": 0}
    spaces = rbac.scope_for_scheduled_work(servable_queryset(Makerspace.objects.all()), field="pk")
    for space in spaces.iterator(chunk_size=100):
        with fanout_tenant_write(space.pk, operation="inventory_stock_snapshot", counts=counts) as permitted:
            if not permitted:
                continue
            try:
                counts["created"] += observe_stock(space, now=now)
            except Exception as exc:
                counts["failed"] += 1
                logger.warning("inventory_stock_snapshot_failed", extra={
                    "makerspace_id": space.pk, "error_class": type(exc).__name__,
                })
    return counts
