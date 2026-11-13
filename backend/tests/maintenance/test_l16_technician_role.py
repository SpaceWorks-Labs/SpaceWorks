"""L16 (#128 C-3): the Technician is the 8th built-in role, with exactly three actions."""

import importlib

import pytest
from django.apps import apps as django_apps
from django.db import connection

from apps.accounts import rbac
from apps.makerspaces.models import MakerspaceRole
from apps.makerspaces.role_catalog import BUILTIN_ROLE_SLUGS, ROLE_BY_SLUG
from tests.maintenance.l16_helpers import world
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db
TECH = {"work_repairs", "run_maintenance", "set_service_state"}


def test_new_spaces_get_eight_builtins_with_the_technician_as_a_combinable_staff_role():
    space = make_space("l16-roles-new")
    slugs = set(MakerspaceRole.objects.filter(makerspace=space).values_list("slug", flat=True))
    assert slugs == set(BUILTIN_ROLE_SLUGS) and "technician" in slugs and len(slugs) == 10  # + shop_manager (L22 #137), fundraising (decision 242m)
    role = MakerspaceRole.objects.get(makerspace=space, slug="technician")
    assert set(role.granted_actions) == TECH and role.is_default and role.is_protected
    assert role.legacy_role == "technician" and ROLE_BY_SLUG["technician"].combinable


def test_the_seed_migration_adds_the_role_to_existing_spaces_once():
    space = make_space("l16-roles-old")
    MakerspaceRole.objects.filter(makerspace=space, slug="technician").delete()
    seed = importlib.import_module("apps.makerspaces.migrations.0122_technician_role_seed").seed

    class Editor:
        pass

    editor = Editor()
    editor.connection = connection
    for _ in range(2):
        seed(django_apps, editor)
    rows = MakerspaceRole.objects.filter(makerspace=space, slug="technician")
    assert rows.count() == 1 and set(rows.get().granted_actions) == TECH


def test_a_technician_holds_no_inventory_money_settings_or_staff_authority():
    w = world("l16-roles-rbac")
    for action in TECH:
        assert rbac.can(w.tech, action, w.space.pk)
    for action in (rbac.Action.EDIT_INVENTORY, rbac.Action.VIEW_INVENTORY, rbac.Action.VIEW_FINANCE,
                   rbac.Action.RECORD_PAYMENT, rbac.Action.MANAGE_MAKERSPACE, rbac.Action.MANAGE_MEMBERS,
                   rbac.Action.MANAGE_MACHINES, rbac.Action.MANAGE_BOOKINGS, rbac.Action.ACCEPT_REQUEST):
        assert not rbac.can(w.tech, action, w.space.pk), action


def test_technician_actions_are_never_organization_grantable():
    assert not TECH & set(rbac.ORGANIZATION_GRANTABLE_ACTIONS)
    assert TECH <= set(rbac.ROLE_GRANTABLE_ACTIONS)
