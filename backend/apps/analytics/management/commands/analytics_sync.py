"""Rebuild the analytics roles, schemas, provisioning functions and curated views now.

``migrate`` already does this after every run; this command is for an operator who granted
the owner role CREATEROLE later, or who wants to see why the sync skipped.
"""

from django.core.management.base import BaseCommand

from apps.analytics.db_sync import sync


class Command(BaseCommand):
    help = "Rebuild the curated analytics views and provisioning functions (lane L25)."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Rebuild even when the fingerprint matches.")

    def handle(self, *args, force=False, **options):
        result = sync(force=force)
        self.stdout.write(f"analytics sync: {result.state}"
                          + (f" ({result.reason})" if result.reason else "")
                          + f", {result.views} views")
        for name, error in sorted(result.failed.items()):
            self.stderr.write(f"  failed {name}: {error}")
        if result.failed:
            raise SystemExit(1)
