"""No force/reset option: the operator supplies exact provider evidence."""
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Reconcile one uncertain account reservation with a provider evidence JSON file."

    def add_arguments(self, parser):
        parser.add_argument("--reservation-id", required=True, type=int)
        parser.add_argument("--operator-id", required=True, type=int)
        parser.add_argument("--evidence-file", required=True)

    def handle(self, *args, **options):
        from django.contrib.auth import get_user_model
        from apps.integrations.mail_providers.reconciliation import reconcile
        from apps.operations.cloud_runtime import writer
        try:
            with Path(options["evidence_file"]).open("rb") as handle:
                raw = handle.read(16385)
            if len(raw) > 16384:
                raise ValueError("email_reconciliation_evidence_too_large")
            evidence = json.loads(raw)
            actor = get_user_model().objects.get(pk=options["operator_id"])
            from apps.operations.cloud_quotas.operator import require_operator
            actor = require_operator(actor)
            refused = False
            with writer("cron") as check:
                check()
                try:
                    state = reconcile(reservation_id=options["reservation_id"], actor=actor, evidence=evidence)
                except (ValueError, TypeError, KeyError):
                    # Invalid evidence has no remote effects, and the atomic
                    # reconciliation rolled back. It is not an uncertain writer.
                    refused = True
            if refused:
                raise ValueError()
        except Exception:
            raise CommandError("Email reconciliation refused; verify exact provider evidence and operator authority.") from None
        self.stdout.write(f"Reservation reconciled: {state}.")
