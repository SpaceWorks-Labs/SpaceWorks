"""Host command: reset one person's two-step sign-in (superadmin rule, on the server shell).

Beside ``recover_superadmin --reset-mfa`` (which recovers the superadmin's own factor):
this one is for people. It clears the authenticator, every passkey and the recovery
codes and ends every session; the reset is audited as ``auth.mfa_reset`` (rule ``host``).
"""

from django.core.management.base import BaseCommand, CommandError

from apps.accounts import mfa_reset
from apps.accounts.models import User
from apps.accounts.staff_identity import is_person


class Command(BaseCommand):
    help = "Reset one person's two-step sign-in (authenticator, passkeys, recovery codes)."

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("--reason", required=True, help="Why (3 to 300 characters); it is audited.")

    def handle(self, *args, **options):
        person = User.objects.filter(username=options["username"]).first()
        if person is None or not is_person(person):
            raise CommandError("No personal account has that username. For the superadmin use "
                               "recover_superadmin --reset-mfa.")
        try:
            mfa_reset.reset(None, person, options["reason"], rule=mfa_reset.RULE_HOST)
        except Exception as exc:
            raise CommandError(str(getattr(exc, "detail", exc))) from exc
        self.stdout.write(f"Two-step sign-in reset for {person.username}; every session ended.")
