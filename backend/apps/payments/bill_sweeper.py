"""Bounded recovery of optional bill issuance, isolated by tenant and payment."""

import logging

from django.db import transaction

from apps.accounts import rbac
from apps.makerspaces.models import Makerspace
from apps.makerspaces.platform import feature_enabled
from apps.tenant_migration.gate_runtime import fanout_tenant_write
from .documents import issue_bill
from .models import Payment

logger = logging.getLogger(__name__)


def issue_missing_bills(*, makerspace_id=None, limit=200):
    if type(limit) is not int or not 1 <= limit <= 10000:
        raise ValueError("Use a bill batch size between 1 and 10000.")
    counts = {"issued": 0, "skipped": 0, "failed": 0}
    spaces = rbac.scope_for_scheduled_work(Makerspace.objects.all(), field="pk").order_by("pk")
    if makerspace_id is not None:
        spaces = spaces.filter(pk=makerspace_id)
    for space in spaces.iterator(chunk_size=100):
        try:
            with fanout_tenant_write(space.pk, operation="issue_missing_bills", counts=counts) as allowed:
                if not allowed:
                    continue
                if not feature_enabled(space, "billing.documents"):
                    continue
                ids = list(Payment.objects.filter(makerspace=space, status="pending")
                           .exclude(documents__kind="bill").order_by("pk").values_list("pk", flat=True)[:limit])
                for pk in ids:
                    try:
                        with transaction.atomic():
                            # Lock before checking pending: settlement may have won the race.
                            payment = Payment.objects.select_for_update().get(pk=pk)
                            if payment.status != "pending" or payment.documents.filter(kind="bill").exists():
                                counts["skipped"] += 1
                                continue
                            if issue_bill(payment):
                                counts["issued"] += 1
                    except Exception as exc:
                        counts["failed"] += 1
                        logger.error("payment_bill_recovery_failed", extra={
                            "payment_id": pk, "failure_type": type(exc).__name__,
                        })
        except Exception as exc:
            counts["failed"] += 1
            logger.error("payment_bill_tenant_failed", extra={
                "makerspace_id": space.pk, "failure_type": type(exc).__name__,
            })
    return counts
