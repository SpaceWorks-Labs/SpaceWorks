"""Decision 295: Makerspace.kind, its setup-area defaults and where the noun is exposed."""
import pytest

from apps.makerspaces.models import Makerspace
from apps.makerspaces.platform import bootstrap_payload
from apps.makerspaces.setup_areas import active_areas
from apps.makerspaces.space_kind import apply_kind_defaults, noun_label, space_noun
from tests.makerspaces.space_pack_helpers import client, person

pytestmark = pytest.mark.django_db
BASE = "/api/v1/admin/makerspaces"


def test_kind_defaults_to_makerspace_and_payload_is_unchanged():
    space = Makerspace.objects.create(name="Plain", slug="plain")
    assert space.kind == "makerspace" and space_noun(space) == "makerspace"
    payload = bootstrap_payload(space)["makerspace"]
    assert "kind" not in payload and "space_noun" not in payload


def test_organization_defaults_turn_events_memberships_bookings_on_inventory_machines_off():
    actor = person("kind-root", superadmin=True)
    space = Makerspace.objects.create(name="Club", slug="club", kind="organization")
    space = apply_kind_defaults(actor, space)
    areas = active_areas(space)
    assert areas["events"] and areas["membership"] and areas["bookings"]
    assert not areas["machines"] and not areas["inventory"]
    # request_workflow is a core module (always installed, lending stays off); only machines is optional.
    assert "machines" not in space.enabled_modules


def test_organization_areas_stay_switchable_later():
    actor = person("kind-switch", superadmin=True)
    space = apply_kind_defaults(actor, Makerspace.objects.create(name="Club", slug="club2", kind="organization"))
    from apps.makerspaces.setup_area_application import apply_areas
    space = apply_areas(actor, space, {"areas": ["events", "membership", "bookings", "inventory"]})
    assert active_areas(space)["inventory"]


def test_bootstrap_exposes_kind_noun_and_organization_page_for_a_workspace():
    from tests.parity_0120.o_b6.helpers import workspace
    space, org = workspace("boot")
    payload = bootstrap_payload(space)["makerspace"]
    assert payload["kind"] == "organization" and payload["space_noun"] == "organization"
    assert payload["organization_page_slug"] == org.slug


def test_noun_label_is_a_translatable_placeholder_value():
    assert noun_label(Makerspace(kind="organization")) == "organization"
    assert noun_label(Makerspace(kind="makerspace")) == "makerspace"


def test_superadmin_creates_an_organization_workspace_through_the_console_api():
    actor = person("kind-create", superadmin=True)
    body = {"name": "Chess Club", "slug": "chess", "public_code": "CHSS", "kind": "organization",
            "organization_name": "Chess Club Inc"}
    response = client(actor).post(BASE, body, format="json")
    assert response.status_code == 201, response.data
    assert response.data["kind"] == "organization" and response.data["space_noun"] == "organization"
    space = Makerspace.objects.get(pk=response.data["id"])
    assert active_areas(space)["events"] and not active_areas(space)["machines"]
    from apps.organizations.models import OrganizationMakerspace
    link = OrganizationMakerspace.objects.get(makerspace=space)
    assert link.relationship == "owner" and link.organization.name == "Chess Club Inc"


def test_kind_cannot_change_after_creation():
    actor = person("kind-lock", superadmin=True)
    space = Makerspace.objects.create(name="Fixed", slug="fixed")
    response = client(actor).patch(f"{BASE}/{space.pk}", {"kind": "organization"}, format="json")
    assert response.status_code == 400 and "kind" in response.data
