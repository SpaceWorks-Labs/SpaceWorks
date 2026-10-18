"""Explicit deployment checkpoints; migrations never activate outbound sending."""
from django.core.management.base import BaseCommand, CommandError

from apps.integrations.notification_cutover import (
    activate, establish_barrier, state, switch_to_canonical, verify,
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
        parser.add_argument("--operator-id", type=int, help="Active platform superadmin responsible for this checkpoint; omitted = system.")

    def handle(self, *args, **options):
        stage = options["stage"]
        try:
            actor = None
            if options.get("operator_id") is not None:
                from apps.accounts.models import User
                actor = User.objects.filter(pk=options["operator_id"], is_active=True,
                    account_kind="platform", role=User.Role.SUPERADMIN).first()
                if actor is None:
                    raise ValueError("Operator must be an active platform superadmin")
            if stage == "barrier":
                establish_barrier(drained=options["old_instances_drained"], actor=actor)
            elif stage == "route":
                switch_to_canonical(actor=actor)
            elif stage == "replay":
                from apps.integrations.notification_ingress import recover
                if not 1 <= options["limit"] <= 10000:
                    raise ValueError("Replay limit must be between 1 and 10000")
                recover(options["limit"])
            elif stage == "verify":
                verify(signoffs={key: options[key + "_reviewed"] for key in ("producer_coverage", "push", "registries")}, actor=actor)
            elif stage == "activate":
                activate(actor=actor)
            current = state()
            self.stdout.write(f"route={current.route} sending_enabled={current.sending_enabled} "
                f"receipt_watermark={current.receipt_watermark} replay_watermark={current.replay_watermark}")
        except (ValueError, RuntimeError) as exc:
            raise CommandError(str(exc)) from exc
