"""Archive confirmation always shows pending charge counts (P1b: superadmin is always on)."""

import pytest
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.test import Client
from django.urls import reverse

from apps.makerspaces.models import Makerspace
from tests.accounts.reauth_helpers import force_recent_control_login
from tests.governance.test_gov_lifecycle import platform

pytestmark = pytest.mark.django_db


def confirmation_for(space):
    client = Client()
    force_recent_control_login(client, platform())
    return client.post(
        reverse("admin:makerspaces_makerspace_changelist"),
        {"action": "archive_makerspaces", ACTION_CHECKBOX_NAME: str(space.pk)},
    )


def test_archive_confirmation_always_shows_pending_charge_counts():
    space = Makerspace.objects.create(name="Money", slug="money-counts")
    response = confirmation_for(space)
    assert response.status_code == 200
    row = response.context_data["makerspaces"][0]
    assert "hidden" not in row
    assert {"owned_pending", "routed_pending", "total_pending"} <= set(row)
    assert "Hidden (superadmin access is off)" not in response.content.decode()
