"""A live superadmin to run `verify_domain`, which now re-checks its actor under lock."""

from apps.accounts.models import User
from tests.return_helpers import make_user


def verify_actor():
    existing = User.objects.filter(username="domain-verify-superadmin").first()
    return existing or make_user("domain-verify-superadmin", role=User.Role.SUPERADMIN)
