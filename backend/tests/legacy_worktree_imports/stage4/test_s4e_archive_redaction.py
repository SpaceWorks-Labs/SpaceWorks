"""Direct archive confirmation never shows a hidden tenant's money counts (review round 5)."""

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


def test_hidden_space_archive_confirmation_omits_pending_charge_counts():
    space = Makerspace.objects.create(name="Hidden money", slug="hidden-money", superadmin_access_enabled=False)
    response = confirmation_for(space)
    assert response.status_code == 200
    row = response.context_data["makerspaces"][0]
    assert row["hidden"] is True
    assert not {"owned_pending", "routed_pending", "total_pending"} & set(row)
    assert "Hidden (superadmin access is off)" in response.content.decode()


def test_visible_space_archive_confirmation_keeps_pending_charge_counts():
    space = Makerspace.objects.create(name="Visible money", slug="visible-money")
    response = confirmation_for(space)
    assert response.status_code == 200
    row = response.context_data["makerspaces"][0]
    assert row["hidden"] is False
    assert {"owned_pending", "routed_pending", "total_pending"} <= set(row)
