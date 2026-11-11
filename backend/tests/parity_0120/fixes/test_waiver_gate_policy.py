"""EV-25: the on-site waiver gate is editable while guest passes are off (presence or membership on)."""
import pytest
from django.urls import reverse

from tests.makerspaces.l4_helpers import features_off, space_with_manager
from tests.return_helpers import authenticated_client

pytestmark = pytest.mark.django_db


def _modules(space, *keys):
    space.refresh_from_db()
    space.enabled_modules = sorted(set(keys))
    space.save(update_fields=["enabled_modules"])
    return features_off(space, "guest_passes")


def test_waiver_gate_patch_allowed_with_passes_off_and_presence_on():
    space, manager = space_with_manager("wg-presence")
    _modules(space, "presence")
    client = authenticated_client(manager)
    url = reverse("admin-guest-pass-policy", args=[space.pk])
    assert client.get(url).status_code == 200
    body = {"waiver_required_on_site": True, "waiver_gate_without_passes": True}
    response = client.patch(url, body, format="json")
    assert response.status_code == 200
    assert response.json()["waiver_gate_without_passes"] is True


def test_other_fields_are_400_while_passes_are_off():
    space, manager = space_with_manager("wg-other")
    _modules(space, "membership")
    client = authenticated_client(manager)
    url = reverse("admin-guest-pass-policy", args=[space.pk])
    response = client.patch(url, {"guest_machine_mode": "supervised"}, format="json")
    assert response.status_code == 400


def test_404_when_neither_presence_nor_membership_nor_passes_are_on():
    space, manager = space_with_manager("wg-none")
    _modules(space)
    client = authenticated_client(manager)
    assert client.get(reverse("admin-guest-pass-policy", args=[space.pk])).status_code == 404
