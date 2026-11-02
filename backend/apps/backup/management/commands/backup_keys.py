"""Host command for platform key rotation (release 2 L11, BK-68). Same services as /control/.

    manage.py backup_keys status
    manage.py backup_keys rotate --kind platform|server --actor-id <superadmin id>
    manage.py backup_keys reencrypt --actor-id <id> [--old-identity-file PATH] [--limit N]
    manage.py backup_keys purge --archive <uuid> --actor-id <id>

``--old-identity-file`` is the PREVIOUS server restore identity, read in place for this run
only (never copied or stored), for one-space archives made before the server key rotated.
A whole-platform archive cannot be re-encrypted on the server: purge it or let it expire.
"""
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User


class Command(BaseCommand):
    help = "Record a backup key rotation and re-encrypt or purge archives on a retired key."

    def add_arguments(self, parser):
        parser.add_argument("action", choices=("status", "rotate", "reencrypt", "purge"))
        parser.add_argument("--kind", choices=("platform", "server"))
        parser.add_argument("--actor-id", type=int)
        parser.add_argument("--old-identity-file")
        parser.add_argument("--limit", type=int, default=50)
        parser.add_argument("--archive")

    def handle(self, *args, **options):
        from apps.backup import archive_reencrypt as reencrypt
        from apps.backup.models import BackupArchive
        from apps.backup.platform_key_rotation import Kind, current_fingerprint, record_rotation, stale_archives

        action = options["action"]
        if action == "status":
            for kind in Kind:
                self.stdout.write(f"{kind.label}: {current_fingerprint(kind) or 'not configured'}")
            for row in stale_archives():
                fixable = "re-encryptable" if reencrypt.can_reencrypt(row, options["old_identity_file"]) else "purge only"
                self.stdout.write(f"stale {row.pk} {row.scope} {row.completed_at:%Y-%m-%d} ({fixable})")
            return
        actor = User.objects.filter(pk=options["actor_id"]).first()
        try:
            from apps.backup.platform_key_rotation import _require_superadmin
            _require_superadmin(actor)
        except Exception:
            raise CommandError("--actor-id must name the active superadmin running this command.") from None
        try:
            if action == "rotate":
                if not options["kind"]:
                    raise CommandError("--kind is required.")
                result = record_rotation(actor, options["kind"])
                self.stdout.write(f"Retired {len(result['retired'])} key(s); {result['stale_archives']} stale archive(s).")
            elif action == "reencrypt":
                done = 0
                for row in stale_archives()[: options["limit"]]:
                    if reencrypt.can_reencrypt(row, options["old_identity_file"]):
                        reencrypt.reencrypt_archive(row, actor=actor, identity_file=options["old_identity_file"])
                        done += 1
                self.stdout.write(f"Re-encrypted {done} archive(s).")
            else:
                row = BackupArchive.objects.filter(pk=options["archive"]).first()
                if row is None:
                    raise CommandError("--archive must name an archive.")
                reencrypt.purge_archive(row, actor=actor)
                self.stdout.write("Purged.")
        except CommandError:
            raise
        except Exception as exc:
            raise CommandError(str(getattr(exc, "detail", exc))) from None
