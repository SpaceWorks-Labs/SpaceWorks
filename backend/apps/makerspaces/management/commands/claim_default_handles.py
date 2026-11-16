from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.makerspaces.public_profile_handles import ensure_default_handle


class Command(BaseCommand):
    help = ("Decision 308(c): give every existing personal account without a username handle its username, "
            "when that is a valid, free handle. Idempotent; the rest choose one at their next sign-in.")

    def handle(self, *args, **options):
        accounts = (get_user_model().objects
                    .filter(account_kind="member", retired_at__isnull=True, merged_into__isnull=True, is_walk_in=False,
                            public_handle__isnull=True)  # reverse join: never NOT IN over the nullable user_id
                    .order_by("pk"))
        claimed = skipped = 0
        for user in accounts.iterator():
            if ensure_default_handle(user):
                claimed += 1
            else:
                skipped += 1
        self.stdout.write(self.style.SUCCESS(f"Handles claimed: {claimed}; left to choose at sign-in: {skipped}."))
