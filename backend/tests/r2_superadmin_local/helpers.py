"""Shared fixtures for the r2-superadmin-controls tests (#185, #187A). Local only."""

from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.makerspaces.models import Makerspace
from tests.accounts.account_factories import make_membership, make_staff
from tests.accounts.reauth_helpers import force_recent_authenticate

REASON = "Paused while the platform reviews a report."


def superadmin(username="controls-root"):
    return User.objects.create_superuser(
        username=username, email=f"{username}@example.test", password="x" * 20,
        account_kind=User.AccountKind.PLATFORM, role=User.Role.SUPERADMIN,
        access_status=User.AccessStatus.ACTIVE,
    )


def space(slug="north-lab", **fields):
    return Makerspace.objects.create(name=slug.replace("-", " ").title(), slug=slug, **fields)


def manager(makerspace, username=None):
    return make_staff(makerspace, username=username or f"{makerspace.slug}-manager",
                      email=f"{makerspace.slug}-manager@example.test")


def member(makerspace, username=None):
    user = User.objects.create_user(username or f"{makerspace.slug}-member",
                                    email=f"{username or makerspace.slug}-member@example.test")
    make_membership(user, makerspace)
    return user


def api(user=None):
    client = APIClient(HTTP_HOST="localhost")
    if user is not None:
        force_recent_authenticate(client, user)
    return client


def control(root, makerspace, action, body=None):
    body = dict(body or {})
    if action == "schedule":  # R4: a schedule ends in a purge, so it takes the typed slug too.
        body.setdefault("confirm_slug", makerspace.slug)
    return api(root).post(f"/api/v1/admin/platform/spaces/{makerspace.pk}/{action}", body, format="json")

