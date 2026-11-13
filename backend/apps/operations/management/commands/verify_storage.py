from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Qualify configured storage using real native operations and runtime credentials."

    def add_arguments(self, parser):
        parser.add_argument("--browser-probes", action="store_true")

    def handle(self, *args, **options):
        from apps.operations.cloud_runtime import writer
        from apps.operations.storage_qualification import verify_bindings
        try:
            with writer("presign") as check:
                results = verify_bindings(check=check)
                if options.get("browser_probes"):
                    import os
                    from cloud_setup.storage_probe import verify_delivery
                    verify_delivery(os.environ, check=check)
        except Exception as exc:
            raise CommandError(getattr(exc, "code", "storage_qualification_failed")) from None
        self.stdout.write(f"Verified {len(results)} storage bindings.")
