"""The stored catalogue is fixed and bootstrap repairs drift."""
import pytest
from django.db import IntegrityError, transaction

from apps.makerspaces.models import MakerspaceRole
from apps.makerspaces.role_catalog import ROLE_CATALOG
from apps.makerspaces.roles import ensure_default_roles
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db
EXPECTED = {
    "space_manager": "Space Manager", "inventory_manager": "Inventory Manager",
    "machine_manager": "Machine Manager", "event_manager": "Event Manager",
    "booking_manager": "Booking Manager", "handover": "Handover", "technician": "Technician", "member": "Member",
    # #137: release 2 adds the built-in Shop Manager (nine fixed roles).
    "shop_manager": "Shop Manager",
    # Decision 242(m): the Fundraising role (ten fixed roles).
    "fundraising": "Fundraising",
}


def test_new_space_has_exactly_the_canonical_builtins():
    space = make_space("fixed-catalog")
    rows = {role.slug: role for role in MakerspaceRole.objects.filter(makerspace=space)}
    assert {slug: role.name for slug, role in rows.items()} == EXPECTED
    for definition in ROLE_CATALOG:
        role = rows[definition.slug]
        assert role.granted_actions == sorted(definition.granted_actions)
        assert role.legacy_role == definition.legacy_role
        assert role.is_default and role.is_protected
    assert rows["handover"].granted_actions == sorted({
        "view_inventory", "assign_box", "issue_request", "issue_direct_loan",
        "return_request", "upload_evidence", "collect_service_request",
    })
    assert rows["member"].granted_actions == []


def test_database_rejects_custom_role():
    space = make_space("fixed-constraint")
    with pytest.raises(IntegrityError, match="makerspacerole_fixed_catalogue"), transaction.atomic():
        MakerspaceRole.objects.create(makerspace=space, name="Custom", slug="custom",
                                     is_default=True, is_protected=True)
    assert MakerspaceRole.objects.filter(makerspace=space).count() == len(EXPECTED)


def test_bootstrap_restores_edited_grants_name_and_legacy_mirror_idempotently():
    space = make_space("fixed-resync")
    role = MakerspaceRole.objects.get(makerspace=space, slug="event_manager")
    MakerspaceRole.objects.filter(pk=role.pk).update(
        name="Changed", granted_actions=["edit_inventory"], legacy_role=None,
    )
    for _ in range(2):
        ensure_default_roles(space)
    role.refresh_from_db()
    assert (role.name, role.legacy_role, role.granted_actions) == (
        "Event Manager", "event_manager", ["manage_events"],
    )
    assert MakerspaceRole.objects.filter(makerspace=space).count() == len(EXPECTED)
