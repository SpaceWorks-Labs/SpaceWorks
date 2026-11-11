"""Shared factories for the audit row-MAC test modules."""
from tests.account_split.sweep_helpers import (
    create_test_user as _create_test_user,
)

from django.contrib.auth import get_user_model

from apps.accounts.models import User
from apps.makerspaces.models import Makerspace


def make_user(username):
    return _create_test_user(
        username=username,
        email=f"{username}@example.test",
        role=User.Role.SPACE_MANAGER,
    )


def make_space(slug):
    return Makerspace.objects.create(name=slug, slug=slug)
