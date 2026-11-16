"""#205: area consoles gate their public-stats editors on public_site_enabled, so every staff row carries it.

Local, untracked. The slim switcher row (roles without VIEW_INVENTORY) must still say whether the public
site is on, and must still withhold the makerspace configuration the full row carries.
"""

import pytest

from apps.admin_api.serializers_makerspace_aux import MakerspaceSwitcherSerializer
from apps.makerspaces.models import Makerspace
from tests.return_helpers import authenticated_client, make_member, make_space

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("enabled", [True, False])
def test_the_slim_switcher_row_carries_public_site_enabled_and_no_config(enabled):
    space = make_space(f"switch-public-{str(enabled).lower()}")
    Makerspace.objects.filter(pk=space.pk).update(public_site_enabled=enabled)
    space.refresh_from_db()
    row = MakerspaceSwitcherSerializer(space).data
    assert row["public_site_enabled"] is enabled
    assert not {"public_api_key", "cors_allowed_origins", "smtp_host", "theme"} & set(row)


@pytest.mark.parametrize("role", ["machine_manager", "booking_manager", "event_manager", "inventory_manager"])
def test_every_area_manager_sees_public_site_enabled_in_the_console_list(role):
    space = make_space(f"switch-list-{role}")
    Makerspace.objects.filter(pk=space.pk).update(public_site_enabled=True)
    manager = make_member(f"switch-list-{role}-user", space, membership_role=role)
    response = authenticated_client(manager).get("/api/v1/admin/makerspaces")
    assert response.status_code == 200, response.content
    rows = [row for row in response.json() if row["id"] == space.pk]
    assert rows and rows[0]["public_site_enabled"] is True
