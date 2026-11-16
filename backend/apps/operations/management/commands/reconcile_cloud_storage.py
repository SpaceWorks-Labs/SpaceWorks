"""Explicit drain plus physical inventory; never release by reservation age."""
import time
import uuid

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Pause managed writers, prove drain, inventory physical bytes and reconcile upload capacity."

    def add_arguments(self, parser):
        parser.add_argument("--operator-id", type=int, required=True)
        parser.add_argument("--max-pages", type=int, default=1000)

    def handle(self, *args, **options):
        from django.conf import settings
        from django.contrib.auth import get_user_model
        from apps.backup.operation_lock import deployment_operation_lock
        from apps.backup.cloud_continuity import operation_guard
        from apps.backup.managed.capture import capture_pause
        from apps.operations.cloud_runtime import writer, check
        from apps.operations.cloud_jobs.contracts import ChunkContext
        from apps.operations.cloud_quotas.sampling import sample_storage_chunk
        from apps.operations.models import CloudObjectAccount
        try:
            actor = get_user_model().objects.get(pk=options["operator_id"])
            from apps.operations.cloud_quotas.operator import require_operator
            actor = require_operator(actor)
            if settings.SPACEWORKS_DEPLOYMENT_PROFILE != "free":
                raise ValueError()
            if not 1 <= options["max_pages"] <= 100000:
                raise ValueError()
            owner = uuid.uuid4()
            with writer("cron"), deployment_operation_lock() as guard, operation_guard(guard), capture_pause(owner):
                # Discard a pre-pause inventory: it cannot prove drained usage.
                CloudObjectAccount.objects.exclude(pk="deployment").update(started_at=None, cursor={})
                checkpoint = {}
                for _ in range(options["max_pages"]):
                    context = ChunkContext(time.monotonic() + 30, check, checkpoint, owner, 0, limit=1)
                    result = sample_storage_chunk(context)
                    if result.complete:
                        break
                    checkpoint = result.checkpoint
                else:
                    raise ValueError("storage_inventory_page_budget_exhausted")
        except Exception:
            raise CommandError("Storage reconciliation refused or incomplete; retain the durable pause for supervised recovery.") from None
        self.stdout.write("Drained physical usage and upload reservations reconciled.")
