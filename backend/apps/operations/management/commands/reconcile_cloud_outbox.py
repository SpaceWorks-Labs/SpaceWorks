"""Exact attempt recovery after all provider claims have independent evidence."""
import re
import uuid

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Reconcile one uncertain outbox task after provider evidence settlement and a proved writer drain."

    def add_arguments(self, parser):
        parser.add_argument("--operator-id", required=True, type=int)
        parser.add_argument("--attempt-token", required=True)
        parser.add_argument("--evidence-sha256", required=True)

    def handle(self, *args, **options):
        from django.conf import settings
        from django.contrib.auth import get_user_model
        from apps.backup.operation_lock import deployment_operation_lock
        from apps.backup.cloud_continuity import operation_guard
        from apps.backup.managed.capture import capture_pause
        from apps.operations.cloud_jobs.reconciliation import reconcile_outbox
        try:
            actor = get_user_model().objects.get(pk=options["operator_id"])
            from apps.operations.cloud_quotas.operator import require_operator
            actor = require_operator(actor)
            if settings.SPACEWORKS_DEPLOYMENT_PROFILE != "free" or settings.SPACEWORKS_DEPLOYMENT_MODE != "managed":
                raise ValueError()
            token = uuid.UUID(options["attempt_token"])
            digest = options["evidence_sha256"]
            if not re.fullmatch(r"[a-f0-9]{64}", digest):
                raise ValueError()
            with deployment_operation_lock() as guard, operation_guard(guard), capture_pause(uuid.uuid4()):
                reconcile_outbox(actor=actor, token=token, evidence_sha256=digest)
        except Exception:
            raise CommandError("Outbox reconciliation refused; settle every provider claim and retain its evidence before recovery.") from None
        self.stdout.write("Specific outbox attempt reconciled; its bounded checkpoint is due again.")
