"""Supervised empty-source handoff; data transfers must complete before this command."""
import uuid

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Verify an empty drained source, qualify its replacement and retain old late-delete credentials."

    def add_arguments(self, parser):
        parser.add_argument("--operator-id", required=True, type=int)
        parser.add_argument("--role", required=True, choices=["private", "public_image", "anchor"])
        parser.add_argument("--replacement-file", required=True)
        parser.add_argument("--retired-destination-id", required=True, type=int)

    def handle(self, *args, **options):
        from django.contrib.auth import get_user_model
        from apps.backup.models import BackupDestination
        from apps.backup.offsite_client import destination_client
        from apps.backup.operation_lock import deployment_operation_lock
        from apps.backup.cloud_continuity import operation_guard
        from apps.backup.managed.capture import capture_pause
        from apps.operations.cloud_quotas.bucket_migration import migrate_empty_binding
        from apps.operations.cloud_quotas.storage_clients import binding_client
        from apps.storage_capabilities.configuration import read_configuration
        from apps.storage_capabilities.runtime import configured_contracts
        source_client = target_client = None
        try:
            actor = get_user_model().objects.get(pk=options["operator_id"])
            from apps.operations.cloud_quotas.operator import require_operator
            actor = require_operator(actor)
            retired = BackupDestination.objects.get(pk=options["retired_destination_id"])
            if retired.enabled:
                raise ValueError()
            role = options["role"]
            source = configured_contracts()[role]
            target = read_configuration(options["replacement_file"])[role]
            owner = uuid.uuid4()
            with deployment_operation_lock() as guard, operation_guard(guard), capture_pause(owner, resume=False):
                from apps.storage_clients import qualification
                with qualification():
                    source_client, target_client = destination_client(retired), binding_client(role, target)
                    receipt = migrate_empty_binding(actor=actor, role=role, source_contract=source,
                        destination_contract=target, source_client=source_client, destination_client=target_client,
                        retired_destination=retired, owner=owner, guard=guard)
        except Exception:
            raise CommandError("Bucket handoff refused; keep the old configuration and any durable pause until reconciled.") from None
        finally:
            if source_client is not None:
                source_client.close()
            if target_client is not None:
                target_client.close()
        self.stdout.write(f"Bucket handoff receipt {receipt.pk}; durable pause owner {owner}. Install the replacement capability file, then run resume_cloud_storage.")
