import uuid
from django.core.management.base import BaseCommand, CommandError
from apps.accounts.models import User
from apps.backup.managed.recovery import recover_pause
from apps.backup.operation_lock import deployment_operation_lock
from apps.backup.cloud_continuity import operation_guard


class Command(BaseCommand):
    help = "Reconcile a stopped managed capture after physical writer and transfer drain."

    def add_arguments(self, parser):
        action = parser.add_mutually_exclusive_group(required=True)
        action.add_argument("--owner", type=uuid.UUID)
        action.add_argument("--describe", action="store_true")
        parser.add_argument("--actor-id", type=int, required=True)

    def handle(self, *args, **options):
        from django.conf import settings
        if settings.SPACEWORKS_DEPLOYMENT_MODE != "managed":
            raise CommandError("This command is managed-only.")
        try:
            actor = User.objects.get(pk=options["actor_id"])
            from apps.tenant_migration.services_import_job import _require_superadmin
            _require_superadmin(actor)
            if options["describe"]:
                import json
                from apps.backup.managed.models import ManagedCaptureState, ManagedWriterBoundary
                state = ManagedCaptureState.objects.get(pk=1)
                self.stdout.write(json.dumps({"owner": str(state.paused_by) if state.paused_by else None,
                    "generation": state.generation, "drain_until": state.drain_until.isoformat() if state.drain_until else None,
                    "unresolved_writers": ManagedWriterBoundary.objects.filter(finished_at=None).count()}))
                return
            with deployment_operation_lock() as guard, operation_guard(guard):
                recover_pause(options["owner"], guard, actor)
        except Exception:
            raise CommandError("Capture recovery refused; retain the pause and inspect writer/transfer proofs.") from None
        self.stdout.write("Managed capture pause reconciled.")
