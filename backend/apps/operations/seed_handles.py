"""Give every seeded personal account a username handle (decision 308).

A personal account without a handle is refused every write (403 `handle_required`) until it chooses
one. `manage.py claim_default_handles` cannot do this for seeded accounts: they have a password, so
by decision 336d their sign-in username is never claimed silently. A seed therefore claims the best
suggestion (a display-name slug, then slug plus digits), exactly as the blocking sign-in step offers.
"""
from django.contrib.auth import get_user_model
from django.db import transaction

from apps.makerspaces.public_profile_handles import claim_for_signup


def claim_seeded_handles() -> int:
    users = (get_user_model().objects
             .filter(account_kind="member", retired_at__isnull=True, merged_into__isnull=True, is_walk_in=False,
                     public_handle__isnull=True)
             .order_by("pk"))
    claimed = 0
    for user in users.iterator():
        with transaction.atomic():
            claimed += claim_for_signup(user) is not None
    return claimed
