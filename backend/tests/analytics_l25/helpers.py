"""Lane L25 local test helpers: spaces with or without `analytics`, staff clients, routes."""

import uuid

from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.makerspaces.models import MakerspaceMembership
from tests.return_helpers import make_member, make_space, make_user

SECRET = "s" * 64


def space(prefix="an", *, analytics=True):
    row = make_space(f"{prefix}-{uuid.uuid4().hex[:6]}")
    modules = set(row.enabled_modules or [])
    modules = modules | {"analytics"} if analytics else modules - {"analytics"}
    row.enabled_modules = sorted(modules)
    row.save(update_fields=["enabled_modules"])
    return row


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def manager(makerspace, name=None):
    return make_member(name or f"sm-{uuid.uuid4().hex[:6]}", makerspace)


def inventory_manager(makerspace):
    return make_member(f"im-{uuid.uuid4().hex[:6]}", makerspace,
                       membership_role=MakerspaceMembership.Role.INVENTORY_MANAGER, role=User.Role.REQUESTER)


def plain_member(makerspace):
    return make_member(f"mem-{uuid.uuid4().hex[:6]}", makerspace, membership_role="custom", role=User.Role.REQUESTER)


def superadmin():
    return make_user(f"root-{uuid.uuid4().hex[:6]}", role=User.Role.SUPERADMIN)


def space_url(name, makerspace, *args):
    return reverse(f"admin-makerspace-analytics{name}", args=[makerspace.pk, *args])


def platform_url(name, *args):
    return reverse(f"admin-platform-analytics{name}", args=list(args))


SPACE_ROUTES = (
    ("get", "", ()), ("get", "-connection", ()), ("patch", "-connection", ()), ("post", "-login", ()),
    ("delete", "-login", ()), ("post", "-login-rotate", ()), ("get", "-embed", (7,)),
)
PLATFORM_ROUTES = SPACE_ROUTES
