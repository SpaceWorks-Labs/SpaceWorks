"""Resume a successful handoff only after verifying its installed replacement."""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Verify the installed bucket replacement and explicitly finish its retained handoff pause."

    def add_arguments(self, parser):
        parser.add_argument("--operator-id", required=True, type=int)
        parser.add_argument("--receipt-id", required=True, type=int)
        parser.add_argument("--pause-owner", required=True)

    def handle(self, *args, **options):
        from django.contrib.auth import get_user_model
        from apps.audit import services as audit
        from apps.backup.operation_lock import deployment_operation_lock
        from apps.backup.cloud_continuity import operation_guard
        from apps.backup.managed.capture import capture_pause
        from apps.operations.models import CloudStorageMigrationReceipt
        from apps.operations.storage_qualification import verify_bindings
        from apps.storage_capabilities.runtime import configured_contracts
        try:
            actor = get_user_model().objects.get(pk=options["operator_id"])
            from apps.operations.cloud_quotas.operator import require_operator
            actor = require_operator(actor)
            receipt = CloudStorageMigrationReceipt.objects.get(pk=options["receipt_id"])
            if str(receipt.pause_owner) != options["pause_owner"]:
                raise ValueError()
            contract = configured_contracts()[receipt.role]
            if contract.identity.fingerprint != receipt.destination_identity:
                raise ValueError()
            with deployment_operation_lock() as guard, operation_guard(guard), capture_pause(options["pause_owner"]):
                verify_bindings(check=guard.assert_valid, roles=[receipt.role])
                audit.record(actor, "storage.bucket_handoff_resumed", target=receipt,
                             meta={"receipt_id": receipt.pk})
        except Exception:
            raise CommandError("Bucket handoff resume refused; retain the pause and verify replacement identity and ownership.") from None
        self.stdout.write("Replacement verified; managed writers may resume with the new generation.")
