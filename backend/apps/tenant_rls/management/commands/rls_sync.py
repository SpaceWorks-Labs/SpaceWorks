from django.core.management.base import BaseCommand, CommandError

from apps.tenant_rls.sync import sync


class Command(BaseCommand):
    help = "Apply the generated row-level security policies (migrate runs this automatically)."

    def add_arguments(self, parser):
        parser.add_argument("--database", default="default")

    def handle(self, *args, **options):
        report = sync(options["database"])
        self.stdout.write(
            f"applied={len(report.applied)} unchanged={report.unchanged} removed={len(report.removed)} "
            f"failed={len(report.failed)} unresolvable={len(report.unresolvable)}")
        for table, error in sorted(report.failed.items()):
            self.stdout.write(f"failed {table}: {error}")
        for label, reason in sorted(report.unresolvable.items()):
            self.stdout.write(f"unresolvable {label}: {reason}")
        if report.failed or report.unresolvable:
            raise CommandError("Some makerspace-scoped tables have no current policy.")
