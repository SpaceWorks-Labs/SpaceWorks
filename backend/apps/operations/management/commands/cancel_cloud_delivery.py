"""Describe an exact intent, then cancel only the reviewed immutable bindings."""
import json
from pathlib import Path
import uuid

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Explicitly cancel an unknown free notification attempt without replay or quota release."

    def add_arguments(self, parser):
        parser.add_argument("--operator-id", type=int, required=True)
        parser.add_argument("--describe", choices=("personal", "channel", "legacy"))
        parser.add_argument("--id")
        parser.add_argument("--evidence-file")

    def handle(self, *args, **options):
        try:
            from django.contrib.auth import get_user_model
            from apps.operations.cloud_jobs.cancellation import cancel, describe, validate, DECISION
            from apps.operations.cloud_quotas.operator import require_operator
            actor = require_operator(get_user_model().objects.get(pk=options["operator_id"]))
            if options["describe"]:
                if not options["id"] or options["evidence_file"]:
                    raise ValueError()
                self.stdout.write(json.dumps(describe(actor, options["describe"], options["id"]), sort_keys=True))
                return
            if options["id"] or not options["evidence_file"]:
                raise ValueError()
            path = Path(options["evidence_file"])
            if not path.is_file() or path.stat().st_size > 16384:
                raise ValueError()
            evidence = json.loads(path.read_text(encoding="utf-8-sig"))
            if evidence.get("decision") != DECISION:
                raise ValueError()
            validate(actor, evidence)
            from apps.backup.operation_lock import deployment_operation_lock
            from apps.backup.cloud_continuity import operation_guard
            from apps.backup.managed.capture import capture_pause
            with deployment_operation_lock() as guard, operation_guard(guard), capture_pause(uuid.uuid4()):
                cancel(actor, evidence)
        except Exception:
            raise CommandError("Cancellation refused; review the exact intent, attempt and binding hashes, then prove writer drain.") from None
        self.stdout.write("Unknown attempt cancelled for future replay; provider acceptance remains unknown and allowances stay charged.")
