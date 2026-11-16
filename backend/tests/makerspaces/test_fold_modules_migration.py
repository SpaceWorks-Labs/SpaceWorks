"""makerspaces/0111 called directly on a head database (#124): keys -> switches, upgrade grants."""
import importlib

import pytest
from django.apps import apps as live_apps
from django.db import connection

from apps.audit.models import AuditLog
from apps.inventory.models import InventoryAsset, InventoryProduct, TrackingMode
from apps.machines.models import Machine, MachineType
from apps.makerspaces.models import Makerspace
from apps.makerspaces.models_settings_authority import ModuleSettingsGrant
from apps.procurement.models import ToBuyItem
from apps.warranty.models import Warranty
from tests.fixed_roles.helpers import staff_account

pytestmark = pytest.mark.django_db
migration = importlib.import_module("apps.makerspaces.migrations.0111_fold_modules_and_settings_grants")


class _Editor:
    connection = connection


def legacy_space(slug, modules, features=()):
    space = Makerspace.objects.create(name=slug, slug=slug)
    Makerspace.objects.filter(pk=space.pk).update(enabled_modules=sorted(modules), enabled_features=sorted(features))
    space.refresh_from_db()
    return space


def test_each_old_module_state_maps_to_per_parent_switches_without_data_loss():
    both = legacy_space("fold-both", {"machines", "maintenance", "procurement", "reports"}, {"reports.saved_views"})
    no_machines = legacy_space("fold-proc", {"procurement"})
    untouched = legacy_space("fold-none", {"machines"})
    item = ToBuyItem.objects.create(makerspace=both, kind="printing", name="PLA")
    kind = MachineType.objects.create(makerspace=untouched, name="Laser", slug="fold-laser")
    machine = Machine.objects.create(makerspace=untouched, machine_type=kind, name="L1")
    product = InventoryProduct.objects.create(makerspace=untouched, name="Meter", tracking_mode=TrackingMode.INDIVIDUAL,
                                              total_quantity=1, available_quantity=1)
    asset = InventoryAsset.objects.create(makerspace=untouched, product=product, asset_tag="FM-1")
    Warranty.objects.create(makerspace=untouched, machine=machine)
    Warranty.objects.create(makerspace=untouched, asset=asset)

    migration.fold(live_apps, _Editor())
    for space in (both, no_machines, untouched):
        space.refresh_from_db()
    assert "maintenance" not in both.enabled_modules and "procurement" not in both.enabled_modules
    assert {"machines.maintenance", "machines.tobuy", "inventory.tobuy", "reports.saved_views"} <= set(both.enabled_features)
    assert set(no_machines.enabled_features) == {"inventory.tobuy"}
    assert {"machines.warranty", "inventory.warranty"} <= set(untouched.enabled_features)
    assert not {"machines.maintenance", "machines.tobuy", "inventory.tobuy"} & set(untouched.enabled_features)
    assert ToBuyItem.objects.filter(pk=item.pk).exists() and Warranty.objects.filter(makerspace=untouched).count() == 2
    retired = AuditLog.objects.filter(action="makerspace.module_retired", makerspace=both)
    assert {row.meta["module"] for row in retired} == {"maintenance", "procurement"}
    # Running again changes nothing.
    migration.fold(live_apps, _Editor())
    assert AuditLog.objects.filter(action="makerspace.module_retired").count() == 3


def test_upgrade_grants_every_current_domain_editor_and_no_space_manager():
    space = Makerspace.objects.create(name="Grant", slug="fold-grant")
    staff_account(space, "fold-sm", "space_manager")
    events = staff_account(space, "fold-em", "event_manager")
    inventory = staff_account(space, "fold-im", "inventory_manager")
    machines = staff_account(space, "fold-mm", "machine_manager")
    migration.grant(live_apps, _Editor())
    rows = {(row.module, row.grantee_id) for row in ModuleSettingsGrant.objects.filter(makerspace=space)}
    assert rows == {("events", events.pk), ("inventory", inventory.pk), ("machines", machines.pk)}
    audits = AuditLog.objects.filter(action="settings.grant_created", makerspace=space)
    assert audits.count() == 3 and {row.meta["via"] for row in audits} == {"migration"}
    migration.grant(live_apps, _Editor())
    assert ModuleSettingsGrant.objects.filter(makerspace=space).count() == 3


def test_a_new_space_starts_with_no_grants():
    space = Makerspace.objects.create(name="Fresh", slug="fold-fresh")
    staff_account(space, "fresh-em", "event_manager")
    assert not ModuleSettingsGrant.objects.filter(makerspace=space).exists()
