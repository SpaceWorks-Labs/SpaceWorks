from django.core.management.base import BaseCommand, CommandError

from apps.payments.bill_sweeper import issue_missing_bills


class Command(BaseCommand):
    help = "Issue missing bills for pending charges (safe to repeat)."

    def add_arguments(self, parser):
        parser.add_argument("--makerspace-id", type=int)
        parser.add_argument("--limit", type=int, default=200)

    def handle(self, *args, **options):
        try:
            counts = issue_missing_bills(makerspace_id=options["makerspace_id"], limit=options["limit"])
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(str(counts))
