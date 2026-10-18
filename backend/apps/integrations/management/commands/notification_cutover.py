"""Explicit deployment checkpoints; migrations never activate outbound sending."""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.integrations.notification_cutover import (
    activate, boundary, establish_barrier, state, switch_to_canonical,
)


class Command(BaseCommand):
    help = "Record the messaging barrier, replay canonical receipts, verify, or explicitly activate."

    def add_arguments(self, parser):
        parser.add_argument("stage", choices=["barrier", "route", "replay", "verify", "activate", "status"])
        parser.add_argument("--old-instances-drained", action="store_true")
        parser.add_argument("--limit", type=int, default=200)
        parser.add_argument("--producer-coverage-reviewed", action="store_true")
        parser.add_argument("--push-reviewed", action="store_true")
        parser.add_argument("--registries-reviewed", action="store_true")

    def handle(self, *args, **options):
        stage = options["stage"]
        try:
            if stage == "barrier":
                establish_barrier(drained=options["old_instances_drained"])
            elif stage == "route":
                switch_to_canonical()
            elif stage == "replay":
                from apps.integrations.notification_ingress import recover
                if not 1 <= options["limit"] <= 10000:
                    raise ValueError("Replay limit must be between 1 and 10000")
                recover(options["limit"])
            elif stage == "verify":
                from apps.integrations.notification_conversion_snapshot import verify_reconciliation
                with boundary(exclusive=True), transaction.atomic():
                    current = state()
                    signoffs = {key: options[key + "_reviewed"] for key in ("producer_coverage", "push", "registries")}
                    if not all(signoffs.values()):
                        raise ValueError("Producer, push and registry sign-offs are required before verification")
                    current.snapshot["_signoffs"] = signoffs
                    current.save(update_fields=["snapshot"])
                    verify_reconciliation()
                    if current.route != "canonical":
                        raise ValueError("Switch to canonical routing and replay first")
                    from apps.integrations.models_cutover import NotificationIngress, NotificationLegacyMapping
                    current.replay_watermark = NotificationIngress.objects.aggregate(n=Max("pk"))["n"] or 0
                    current.snapshot["_verified"] = {"watermark": current.replay_watermark,
                        "receipt_count": NotificationIngress.objects.count(),
                        "mapping_count": NotificationLegacyMapping.objects.count(),
                        "verified_at": timezone.now().isoformat()}
                    current.reconciled_at = timezone.now()
                    current.save(update_fields=["reconciled_at", "replay_watermark", "snapshot"])
            elif stage == "activate":
                activate()
            current = state()
            self.stdout.write(f"route={current.route} sending_enabled={current.sending_enabled} "
                f"receipt_watermark={current.receipt_watermark} replay_watermark={current.replay_watermark}")
        except (ValueError, RuntimeError) as exc:
            raise CommandError(str(exc)) from exc
