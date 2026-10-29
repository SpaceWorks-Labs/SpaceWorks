"""Finite maintenance-only Lane D producer, distinct from ordinary tenant archives."""
from pathlib import Path
import shutil
from django.core.management.base import BaseCommand, CommandError
from apps.accounts.models import User
from apps.makerspaces.models import Makerspace


class Command(BaseCommand):
    help = "Build the existing portable tenant dump through qualified managed scratch storage."

    def add_arguments(self, parser):
        parser.add_argument("--makerspace", required=True)
        parser.add_argument("--actor-id", type=int, required=True)
        parser.add_argument("--output", required=True)
        parser.add_argument(
            "--recipient", action="append", required=True, dest="recipients",
            help="Tenant age public key for this export only; repeat for more keys. "
            "The platform key is always added to the outer envelope.",
        )

    def handle(self, *args, **options):
        from apps.tenant_migration.services_import_job import _require_superadmin
        from apps.tenant_migration.tenant_dump_capture import request_tenant_dump_capture, capture_tenant_dump_source
        from apps.tenant_migration.tenant_dump_derivation import derive_tenant_dump
        from apps.tenant_migration.tenant_dump_publication import register_unpublished_artifact, publish_tenant_dump
        try:
            actor = User.objects.get(pk=options["actor_id"])
            _require_superadmin(actor)
            output = Path(options["output"])
            if output.exists() or not output.parent.is_dir():
                raise ValueError
            makerspace = Makerspace.objects.get(slug=options["makerspace"])
            capture = request_tenant_dump_capture(
                actor, makerspace, recipients=options["recipients"]
            )
            capture_tenant_dump_source(capture.pk)
            artifact, _manifest = derive_tenant_dump(capture.pk)
            # Preserve the same existing artifact/format. Publication revalidates
            # source money and lineage before the local copy is handed out.
            register_unpublished_artifact(capture.pk, artifact)
            with artifact.open("rb") as source, output.open("xb") as destination:
                output.chmod(0o600)
                shutil.copyfileobj(source, destination, 1024 * 1024)
            try:
                published, _token = publish_tenant_dump(capture.pk)
            except BaseException:
                output.unlink(missing_ok=True)
                raise
        except Exception:
            raise CommandError("Portable export refused; inspect capability, recipient and capture audit codes.") from None
        self.stdout.write(f"Portable dump SHA-256: {published.artifact_sha256}")
