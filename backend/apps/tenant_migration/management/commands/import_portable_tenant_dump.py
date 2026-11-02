"""Import a self-host move archive on a fresh server (release 2 L11, #128 C-23).

    manage.py import_portable_tenant_dump --archive move.tar.age --sha256 <digest> \
        --actor-id <this server's superadmin id> [--slug new-slug] [--decisions decisions.json] [--no-activate]

The archive must have been exported with THIS server's ``TENANT_MIGRATION_AGE_RECIPIENT``
as the one-shot key. It runs the ordinary admission, staging, identity-decision and
materialization pipeline; every person is created (staff keep their roles and everyone
keeps their sign-in) unless ``--decisions`` (a JSON list of import identity decisions)
says otherwise. An email this server already holds refuses the import until decided.
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User


class Command(BaseCommand):
    help = "Import a PORTABLE tenant archive handed over for a self-host move, then activate the space."

    def add_arguments(self, parser):
        parser.add_argument("--archive", required=True)
        parser.add_argument("--sha256", required=True)
        parser.add_argument("--actor-id", type=int, required=True)
        parser.add_argument("--slug")
        parser.add_argument("--decisions")
        parser.add_argument("--no-activate", action="store_true")

    def handle(self, *args, **options):
        from apps.tenant_migration.selfhost_move_import import import_selfhost_move

        archive = Path(options["archive"])
        if not archive.is_file():
            raise CommandError("--archive must name the encrypted archive file.")
        decisions = None
        if options["decisions"]:
            try:
                decisions = json.loads(Path(options["decisions"]).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                raise CommandError("--decisions must be a readable JSON list.") from None
        actor = User.objects.filter(pk=options["actor_id"]).first()
        try:
            job = import_selfhost_move(actor, archive, options["sha256"].strip().lower(), slug=options["slug"],
                                       decisions=decisions, activate=not options["no_activate"])
        except Exception as exc:
            code = getattr(exc, "code", "") or type(exc).__name__
            detail = getattr(exc, "detail", None) or getattr(exc, "messages", None) or str(exc)
            raise CommandError(f"Import refused ({code}): {detail}") from None
        space = job.target_makerspace
        self.stdout.write(self.style.SUCCESS(f"Imported {space.name} as /{space.slug} ({space.lifecycle_state})."))
