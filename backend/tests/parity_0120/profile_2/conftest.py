"""PROFILE-2 fixtures: two spaces, three accounts, and a logged-out client."""
import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.makerspaces.models import Makerspace, MakerspaceMembership, MakerspaceRole

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def platform_host(settings):
    settings.INFRA_HOSTS = {*settings.INFRA_HOSTS, "testserver"}


def make_space(slug, **fields):
    return Makerspace.objects.create(name=slug.title(), slug=slug, **fields)


def make_person(username, *spaces, display_name=""):
    user = User.objects.create_user(
        username=username, email=f"{username}@example.test",
        display_name=display_name or username.title(), access_status=User.AccessStatus.ACTIVE)
    for space in spaces:
        MakerspaceMembership.objects.create(
            user=user, makerspace=space, role=MakerspaceMembership.Role.CUSTOM, status="active",
            assigned_role=MakerspaceRole.objects.get(makerspace=space, slug="member"))
    return user


def client_for(user=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user=user)
    return client


@pytest.fixture
def space_a():
    return make_space("space-a")


@pytest.fixture
def space_b():
    return make_space("space-b")


@pytest.fixture
def ada(space_a, space_b):
    return make_person("ada", space_a, space_b)


@pytest.fixture
def grace(space_a):
    return make_person("grace", space_a)


@pytest.fixture
def stranger():
    return make_person("stranger")
