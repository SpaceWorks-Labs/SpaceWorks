import pytest
from cryptography.fernet import Fernet
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.makerspaces.models import Makerspace
from tests.fixed_roles.helpers import assign_builtin_roles, staff_account


@pytest.fixture(autouse=True)
def messaging_configuration(settings):
    settings.MESSAGING_WEBHOOK_BASE_URL = "https://callbacks.example.test"
    settings.WHATSAPP_GRAPH_VERSION = "v23.0"
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode()


@pytest.fixture
def space(db):
    return Makerspace.objects.create(name="Messaging lab", slug="messaging-lab")


@pytest.fixture
def member(space):
    user = User.objects.create_user(username="messaging-member", phone_e164="+14155552671",
                                    phone_verified_at=timezone.now())
    assign_builtin_roles(user, space, "member")
    return user


@pytest.fixture
def manager(space):
    # Staff authority lives on a separate tenant-bound STAFF account (account kinds).
    return staff_account(space, "messaging-manager", "space_manager")


@pytest.fixture
def client():
    return APIClient()
