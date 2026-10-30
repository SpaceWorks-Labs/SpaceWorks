"""Host-side: turn one space of a decrypted whole-platform backup into a restore point.

Decrypt the archive on the host first, with the offline platform key, never on the
server; then run this with the decrypted directory. See docs/self-hosting.md.
"""

from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User
from apps.backup.space_extract import extract_space_restore_point
from apps.backup.space_restore_plan import SpaceRestoreError
from apps.makerspaces.models import Makerspace


class Command(BaseCommand):
    help = "Extract one makerspace from a DECRYPTED whole-platform backup as a per-space restore point."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True, help="The platform superadmin recorded as the actor.")
        parser.add_argument("--source", required=True, help="The decrypted whole-platform archive directory.")
        parser.add_argument("--makerspace", required=True, help="The makerspace id or slug to extract.")

    def handle(self, *args, **options):
        actor = User.objects.filter(username=options["username"]).first()
        value = options["makerspace"]
        lookup = {"pk": int(value)} if value.isdigit() else {"slug": value}
        makerspace = Makerspace.objects.filter(**lookup).first()
        if actor is None or makerspace is None:
            raise CommandError("Unknown superadmin or makerspace.")
        try:
            archive = extract_space_restore_point(actor, options["source"], makerspace)
        except SpaceRestoreError as exc:
            raise CommandError(f"[{exc.code}] {exc}") from None
        self.stdout.write(f"Restore point {archive.pk} is ready for {makerspace.slug}; "
                          "restore it from the Backup and restore page.")
