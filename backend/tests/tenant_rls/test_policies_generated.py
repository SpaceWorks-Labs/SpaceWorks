"""A1 policies: generated from the classification, applied post-migrate, guarded."""

import pytest
from django.core.checks import run_checks
from django.db import connection, transaction

from apps.tenant_rls.checks import coverage_gaps
from apps.tenant_rls.context import capability_context, tenant_context
from apps.tenant_rls.policies import FIXED_ROLE, TENANT_POLICY, build_plans
from apps.tenant_rls.scope_registry import EXEMPT, predicates
from apps.tenant_rls.sync import sync

from .conftest import labels

pytestmark = pytest.mark.django_db


def test_every_scoped_model_compiles_and_none_is_unresolvable():
    plans, unresolvable = build_plans()
    assert unresolvable == {}
    assert set(plans) == set(predicates())
    assert len(plans) > 300
    for label in ("hardware_requests.HardwareRequest", "hardware_requests.HardwareRequestItem",
                  "boxes.Box", "audit.AuditLog", "encryption.PiiBlindIndex", "encryption.KeyRotationJob"):
        assert label in plans, label


def test_exemptions_are_the_pinned_closed_list():
    assert set(EXEMPT) == {"makerspaces.Makerspace", "tenant_rls.FixedRoleScope"}
    plans, _ = build_plans()
    assert not set(EXEMPT) & set(plans)


def test_post_migrate_applied_every_policy_and_sync_is_idempotent():
    assert coverage_gaps() == []
    first = sync()
    assert first.applied == [] and first.failed == {} and first.unchanged == len(build_plans()[0])


def test_guard_reports_a_missing_policy_and_sync_restores_it():
    with connection.cursor() as cursor:
        cursor.execute(f'DROP POLICY {TENANT_POLICY} ON "boxes_box"')
    assert "boxes_box" in coverage_gaps()
    warnings = [message for message in run_checks(databases=["default"]) if message.id == "tenant_rls.W001"]
    assert warnings and "boxes_box" in warnings[0].msg
    assert "boxes_box" in sync().applied
    assert coverage_gaps() == []


def test_static_guard_is_clean():
    assert not [message for message in run_checks() if message.id == "tenant_rls.E001"]


def test_a_new_direct_foreign_key_table_is_covered_without_a_hand_list():
    # KeyRotationJob is OMITTED from exports (no dataset predicate) yet carries a makerspace FK.
    assert predicates()["encryption.KeyRotationJob"].any_paths == ("makerspace",)


def test_multi_hop_policy_scopes_child_rows(probe, spaces):
    from django.contrib.auth import get_user_model
    from apps.hardware_requests.models import HardwareRequest, HardwareRequestItem
    from apps.inventory.models import InventoryProduct as Product
    a, b = spaces
    user = get_user_model().objects.create_user(username="rls-hop")
    items = []
    for space in (a, b):
        product = Product.objects.create(makerspace=space, name=f"Hop {space.slug}")
        request = HardwareRequest.objects.create(makerspace=space, requester=user, requester_username="rls-hop")
        items.append(HardwareRequestItem.objects.create(request=request, product=product, requested_quantity=1))
    ids = [item.pk for item in items]
    with tenant_context(a.pk):
        assert list(HardwareRequestItem.objects.filter(pk__in=ids).values_list("pk", flat=True)) == [items[0].pk]
    with capability_context("backup", label="test"):
        assert HardwareRequestItem.objects.filter(pk__in=ids).count() == 2


def test_fixed_role_policy_pins_a_login_whatever_settings_it_sends(probe, boxes):
    from apps.tenant_rls.models import FixedRoleScope
    a, _b = (box.makerspace for box in boxes)
    with connection.cursor() as cursor:
        # L25's post-migrate sync creates the group on the test database already.
        cursor.execute(f"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{FIXED_ROLE}') "
                       f'THEN CREATE ROLE "{FIXED_ROLE}" NOLOGIN; END IF; END $$')
        cursor.execute('CREATE ROLE "rls_fixed_analytics_a" NOLOGIN NOBYPASSRLS')
        cursor.execute(f'GRANT "{FIXED_ROLE}" TO "rls_fixed_analytics_a"')
        cursor.execute('GRANT SELECT ON "boxes_box" TO "rls_fixed_analytics_a"')
        cursor.execute('GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO "rls_fixed_analytics_a"')
    FixedRoleScope.objects.create(role_name="rls_fixed_analytics_a", makerspace=a)
    with connection.cursor() as cursor:
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")  # no pending FK events before policy DDL
    result = sync(tables={"boxes_box"})
    # The fixed-role policy is already current when L25's post-migrate sync created the group
    # before the policies were applied; otherwise this sync applies it. Either way it must hold.
    assert result.failed == {} and (result.applied == ["boxes_box"] or result.unchanged == 1)
    with connection.cursor() as cursor:
        raw = cursor.cursor
        raw.execute('SET LOCAL ROLE "rls_fixed_analytics_a"')
        raw.execute("SELECT set_config('app.rls_bound', 'on', true), set_config('app.rls_capability', 'backup', true)")
        raw.execute("SELECT label FROM boxes_box WHERE label IN ('A box', 'B box') ORDER BY label")
        seen = [row[0] for row in raw.fetchall()]
        raw.execute("SET LOCAL ROLE NONE")
    assert seen == ["A box"]
    assert labels() == ["A box", "B box"]


def test_every_generated_policy_evaluates_under_a_binding(probe, spaces):
    """No policy errors or recurses: every policed table is readable bound, open and by capability."""
    plans, _ = build_plans()
    a = spaces[0]
    failures = {}
    for plan in plans.values():
        for binding in (lambda: tenant_context(a.pk), lambda: capability_context("backup", label="all")):
            try:
                with transaction.atomic(), binding(), connection.cursor() as cursor:
                    cursor.execute(f'SELECT count(*) FROM "{plan.table}"')
            except Exception as exc:  # noqa: BLE001 - collect every table, then fail once
                failures[plan.table] = str(exc)[:200]
                break
    assert failures == {}
