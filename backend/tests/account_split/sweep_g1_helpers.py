"""Explicit staff actors for tests whose older domain builders made members."""

from tests.accounts.account_factories import make_staff


def event_staff(space, username="checkin-staff"):
    return make_staff(space, username=f"{username}-{space.slug}",
                      email=f"{username}-{space.slug}@example.test", access_status="active")


def direct_admin(space):
    return make_staff(space, username=f"direct-admin-{space.slug}", access_status="active")
