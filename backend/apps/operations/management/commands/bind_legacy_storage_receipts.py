from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Bind pre-identity late-delete receipts to the verified CURRENT private bucket before any migration."

    def add_arguments(self, parser):
        parser.add_argument("--operator-id", required=True, type=int)

    def handle(self, *args, **options):
        from django.contrib.auth import get_user_model
        from apps.operations.cloud_runtime import writer
        from apps.operations.cloud_quotas.receipt_storage import bind_legacy_receipts
        try:
            actor = get_user_model().objects.get(pk=options["operator_id"])
            from apps.operations.cloud_quotas.operator import require_operator
            actor = require_operator(actor)
            with writer("cron"):
                count = bind_legacy_receipts(actor=actor)
        except Exception:
            raise CommandError("Receipt binding refused; qualify the existing bucket before changing its configuration.") from None
        self.stdout.write(f"Bound {count} legacy receipts.")
