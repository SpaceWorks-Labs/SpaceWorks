"""Catalog, authority and disclosure contracts for every A+B definition."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts import rbac
from apps.makerspaces.models import MakerspaceMembership
from apps.operations.org_report_aggregate import aggregate_rows, COMBINE_FUNCTIONS
from apps.operations.org_report_scope import EXCLUDED_ORGANIZATION_REPORT_KEYS
from apps.operations.org_report_strategies import STRATEGIES
from apps.operations.report_definitions_ab import AB_REPORT_KEYS
from apps.operations.report_registry import REPORT_DEFINITIONS, report_definition
from apps.operations.report_types import ReportNotFound, ReportResult
from apps.operations.report_validation import validate_report_definition
from apps.operations.reports import report_data, report_rows
from apps.operations.report_output import project_report_output
from tests.operations.report_assertions import assert_report_disclosure_safe
from tests.return_helpers import authenticated_client, make_member, make_product, make_space, make_user


@pytest.mark.parametrize("key", sorted(AB_REPORT_KEYS))
def test_catalog_privacy_chart_and_organization_contracts(key):
    definition = report_definition(key)
    validate_report_definition(definition)
    assert sum(d.key == key for d in REPORT_DEFINITIONS) == 1
    assert definition.chart_spec is not None
    if definition.grains:
        assert definition.grains == ("day", "week", "month")
    if definition.identity_bearing:
        assert not definition.schedulable and not definition.deployment_aggregate
        assert key in EXCLUDED_ORGANIZATION_REPORT_KEYS and key not in STRATEGIES
        with pytest.raises(ReportNotFound):
            report_data(key)
    else:
        assert definition.deployment_aggregate
        assert definition.schedulable == (key != "summary")
        assert "makerspace_id" in definition.fields
        assert key in STRATEGIES and key in COMBINE_FUNCTIONS
        assert set(STRATEGIES[key].total_fields) == set(definition.fields) - {"makerspace_id"}
    assert_report_disclosure_safe(definition.chart_spec)


@pytest.mark.django_db
@pytest.mark.parametrize("key", sorted(AB_REPORT_KEYS))
def test_preview_fields_are_allowlisted_and_other_tenant_does_not_appear(key):
    space, other = make_space("ab-scope"), make_space("ab-other")
    actor = make_member("ab-scope-manager", space)
    foreign_actor = make_member("FOREIGN-SENTINEL", other)
    definition = report_definition(key)
    # Enable actual prerequisites, including opt-in modules, without changing the other tenant.
    from tests.analytics.test_ab_inventory_m1f2 import seed_sources
    own = seed_sources(space, actor, "Own")
    foreign = seed_sources(other, foreign_actor, "FOREIGN-SENTINEL")
    response = report_data(key, space.pk, actor=actor)
    assert "FOREIGN-SENTINEL" not in str(response)
    assert_report_disclosure_safe(response, aggregate=not definition.identity_bearing)
    if "typed_rows" in response:
        assert all(set(row) <= set(definition.fields) for row in response["typed_rows"])
        for row in response["typed_rows"]:
            for field in ("product_id", "asset_id", "request_id", "actor_id", "pool_id", "item_id"):
                if row.get(field) is not None:
                    assert row[field] != foreign.get(field)
        assert response["typed_rows"], f"Seed did not exercise {key}"
    else:
        assert set(response) <= set(definition.fields)
        assert response["products"] == 1
    if definition.exportable:
        exported = report_rows(key, space.pk, actor=actor)
        assert set(exported[0]) <= set(definition.fields)
        assert "FOREIGN-SENTINEL" not in str(exported)
        assert_report_disclosure_safe(exported, aggregate=not definition.identity_bearing)


@pytest.mark.django_db
@pytest.mark.parametrize("key", sorted(AB_REPORT_KEYS))
def test_source_module_off_blocks_http_and_direct_source_queries(key):
    definition = report_definition(key)
    if not definition.required_modules:
        return  # inventory-control is an optional-section composite.
    space = make_space("ab-gating")
    actor = make_member("ab-gating-manager", space)
    # A source is a module key, a capability key (`machines.tobuy`) or an any-of pair of capabilities
    # (report_sources); switch every part off, each in the field that stores it.
    from apps.operations.report_sources import is_capability, parts
    off = parts(definition.required_modules[0])
    space.enabled_modules = sorted((set(space.enabled_modules) | {"reports"}) - {p for p in off if not is_capability(p)})
    space.enabled_features = sorted(set(space.enabled_features or []) - {p for p in off if is_capability(p)})
    space.save(update_fields=["enabled_modules", "enabled_features"])
    response = authenticated_client(actor).get(reverse("analytics-generic", args=[space.pk, key]))
    assert response.status_code == 404
    kwargs = {"actor": actor} if key in {"consumable-usage", "consumable-pools", "procurement-performance",
                                            "overdue-loans", "longest-loans", "qr-scan-actors"} else {}
    data = definition.builder()(space.pk, **kwargs)
    assert not data.records if isinstance(data, ReportResult) else not any(data.values())


@pytest.mark.django_db
@pytest.mark.parametrize("key", sorted(AB_REPORT_KEYS))
def test_member_has_no_staff_report_authority(key):
    space = make_space("ab-member-denied")
    from tests.fixed_roles.helpers import assign_builtin_roles
    actor = make_user("ab-member", access_status="active")
    assign_builtin_roles(actor, space, "member")
    response = authenticated_client(actor).get(reverse("analytics-generic", args=[space.pk, key]))
    assert response.status_code in (403, 404)


@pytest.mark.django_db
@pytest.mark.parametrize("key", sorted(AB_REPORT_KEYS - {"overdue-loans", "longest-loans", "qr-scan-actors"}))
def test_deployment_rows_carry_tenant_identity(key):
    from apps.operations.report_scope import eligible_makerspace_ids
    space = make_space("ab-deployment")
    make_product(space)
    definition = report_definition(key)
    space.enabled_modules = sorted(set(space.enabled_modules) | {"reports"} | set(definition.required_modules))
    space.save(update_fields=["enabled_modules"])
    data = definition.builder()(None)
    assert isinstance(data, ReportResult)
    assert "makerspace_id" in data.field_order
    allowed = set(eligible_makerspace_ids(*definition.required_modules))
    assert all(row["makerspace_id"] in allowed for row in data.records)
    assert_report_disclosure_safe(project_report_output(definition, data).records)


def test_organization_rates_sum_numerators_and_denominators():
    rows = [(1, [dict(product_id=1, product_name="A", damaged_quantity=1, lost_quantity=0, total_quantity=1)]),
            (2, [dict(product_id=1, product_name="A", damaged_quantity=0, lost_quantity=1, total_quantity=9)])]
    total = aggregate_rows("damaged-lost", rows, limit=100)[0]
    assert total["damage_rate_percent"] == total["loss_rate_percent"] == 10
    assert_report_disclosure_safe(total)
    rows = [(1, [dict(period="2026-10-01", resolved_count=1, resolution_hours=2)]),
            (2, [dict(period="2026-10-01", resolved_count=9, resolution_hours=90)])]
    assert aggregate_rows("problem-reports", rows, limit=100)[0]["average_resolution_hours"] == 9.2


def test_organization_consumption_never_merges_units_or_currencies():
    base = dict(period="2026-10-01", source="pooled_service", material="Material", consumed_quantity=2,
                reserved_quantity=0, adjusted_quantity=0, cost_unknown_quantity=0, cost_total_minor=200)
    rows = [(1, [dict(base, measurement_unit="grams", currency="USD")]),
            (2, [dict(base, measurement_unit="milliliters", currency="USD"),
                 dict(base, measurement_unit="grams", currency="INR")])]
    combined = aggregate_rows("consumable-usage", rows, limit=100)
    assert len(combined) == 3
    assert all(row["consumed_quantity"] == 2 and row["cost_total_minor"] == 200 for row in combined)
    assert_report_disclosure_safe(combined)
