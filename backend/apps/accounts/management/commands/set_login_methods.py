from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.login_methods_services import BUILTIN_PROVIDERS, parse_providers, update_login_methods


class Command(BaseCommand):
    help = "Change install-time two-step sign-in and built-in provider choices safely."

    def add_arguments(self, parser):
        parser.add_argument("--mfa", choices=("on", "off"))
        parser.add_argument("--providers", help="Comma list: google,apple,github; empty or none disables all.")

    def handle(self, *args, **options):
        changes = {}
        try:
            if options["mfa"] is not None:
                changes["mfa_enabled"] = options["mfa"] == "on"
            if options["providers"] is not None:
                selected = parse_providers(options["providers"])
                changes.update({f"{provider}_enabled": provider in selected for provider in BUILTIN_PROVIDERS})
            if not changes:
                raise CommandError("Supply --mfa and/or --providers.")
            update_login_methods(changes)
        except ValidationError as exc:
            raise CommandError("; ".join(exc.messages)) from exc
        self.stdout.write(self.style.SUCCESS("Platform login methods updated."))
