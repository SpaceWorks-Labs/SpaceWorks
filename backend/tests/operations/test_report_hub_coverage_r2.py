"""Decision 327: every module reports, every report declares its source and action, and the 0.12
reports follow their module switch, stay per-space and group like the module screens."""

import pytest
from rest_framework.test import APIClient

from apps.accounts import rbac
from apps.makerspaces.module_registry import GROUPS, MODULE_KEYS
from apps.operations.org_report_scope import EXCLUDED_ORGANIZATION_REPORT_KEYS
from apps.operations.report_coverage import REPORT_MODULE_COVERAGE
from apps.operations.report_definitions_r2_final import R2_FINAL_REPORT_KEYS
from apps.operations.report_groups import PLATFORM_GROUP, report_group
from apps.operations.report_registry import REPORT_REGISTRY
from apps.operations.report_validation import validate_report_definition
from tests.return_helpers import make_member, make_space

HEALTH_ONLY = {"module-operational-health"}
# A module with nothing but the shared health row must be named here WITH the reason; the test
# also fails when a listed module gains a real report, so an exemption cannot outlive its cause.
EXEMPT_MODULES = {
    "event_reimbursements": "Claims are reported as money by the finance-events and event-finance ledgers.",
    "analytics": "A read-only database login: its views are the report, and activity shows in audit-activity.",
}
TENANT_KEYS = sorted(R2_FINAL_REPORT_KEYS - {"platform-profile-adoption"})
SOURCE = {"device-adapter-activity": "devices", "machine-access-grants": "machines",
          "card-studio-activity": "membership", "event-certificates-issued": "events", "report-usage": "reports"}


def test_every_module_has_a_report_beyond_the_health_row_or_a_stated_exemption():
    bare = {module for module in MODULE_KEYS
            if set(REPORT_MODULE_COVERAGE[module].reports) <= HEALTH_ONLY}
    assert bare == set(EXEMPT_MODULES), (bare, set(EXEMPT_MODULES))
    assert all(reason.strip() for reason in EXEMPT_MODULES.values())


def test_every_registered_report_declares_a_source_an_action_and_a_group():
    valid_actions = set(rbac.ALL_ACTIONS)
    group_keys = {group.key for group in GROUPS} | {PLATFORM_GROUP}
    for definition in REPORT_REGISTRY.values():
        assert definition.required_action in valid_actions, definition.key
        assert all(action in valid_actions for action in definition.alternate_actions), definition.key
        declared = (definition.required_modules or definition.section_modules or definition.required_feature
                    or definition.platform_only or definition.subject_kind
                    or any(definition.key in coverage.reports for coverage in REPORT_MODULE_COVERAGE.values()))
        # A report that reads no switch at all is a loan-spine report and sits in the always-on group.
        assert declared or report_group(definition) == "inventory", definition.key
        assert report_group(definition) in group_keys, definition.key


@pytest.mark.parametrize("key", sorted(R2_FINAL_REPORT_KEYS))
def test_new_reports_are_valid_counts_only_and_never_combine_across_an_organization(key):
    definition = REPORT_REGISTRY[key]
    validate_report_definition(definition)
    assert definition.required_action and not definition.identity_bearing
    assert key in EXCLUDED_ORGANIZATION_REPORT_KEYS
    assert not any(marker in field for field in definition.fields for marker in ("name", "email", "phone", "handle"))
    if key == "platform-profile-adoption":
        assert definition.platform_only and not definition.schedulable
    else:
        assert definition.required_modules == (SOURCE[key],) and definition.schedulable and definition.exportable


def test_new_reports_group_with_their_module_screens():
    expected = {"device-adapter-activity": "devices", "machine-access-grants": "machines",
                "card-studio-activity": "membership", "event-certificates-issued": "events",
                "report-usage": "reports", "platform-profile-adoption": PLATFORM_GROUP}
    assert {key: report_group(REPORT_REGISTRY[key]) for key in expected} == expected


def _space(slug, *modules):
    space = make_space(slug)
    space.enabled_modules = sorted(set(space.enabled_modules or []) | {"reports", *modules})
    space.save(update_fields=["enabled_modules"])
    return space


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.mark.django_db
@pytest.mark.parametrize("key", TENANT_KEYS)
def test_new_report_is_gated_by_its_module_and_appears_grouped(key):
    module = SOURCE[key]
    space = _space(f"r2-gate-{key[:10]}", module)
    manager = make_member(f"r2-gate-{key[:10]}-m", space)
    base = f"/api/v1/admin/makerspace/{space.pk}"
    entries = {row["key"]: row for row in _client(manager).get(f"{base}/reports/catalog").json()["results"]}
    assert key in entries and entries[key]["group"] == report_group(REPORT_REGISTRY[key])
    assert entries[key]["group_label"] and isinstance(entries[key]["group_order"], int)
    assert _client(manager).get(f"{base}/analytics/{key}").status_code == 200
    export = _client(manager).get(f"{base}/reports/{key}/export", {"format": "csv"})
    assert export.status_code == 200
    if module != "reports":
        space.enabled_modules = [m for m in space.enabled_modules if m != module]
        space.save(update_fields=["enabled_modules"])
        entries = {row["key"] for row in _client(manager).get(f"{base}/reports/catalog").json()["results"]}
        assert key not in entries
        assert _client(manager).get(f"{base}/analytics/{key}").status_code == 404


@pytest.mark.django_db
def test_device_adapter_report_counts_only_its_own_space():
    from apps.devices.models import Device
    mine, other = _space("r2-dev-mine", "devices"), _space("r2-dev-other", "devices")
    Device.objects.create(makerspace=mine, kind=Device.Kind.ADAPTER, name="Door", status=Device.Status.ACTIVE,
                          public_key="k" * 43, key_fingerprint="f" * 64)  # an active device must hold a key
    manager = make_member("r2-dev-mine-m", mine)
    rows = _client(manager).get(f"/api/v1/admin/makerspace/{mine.pk}/analytics/device-adapter-activity").json()["rows"]
    assert {row[0]: row[1] for row in rows[1:]}["adapters_active"] == 1
    other_manager = make_member("r2-dev-other-m", other)
    rows = _client(other_manager).get(f"/api/v1/admin/makerspace/{other.pk}/analytics/device-adapter-activity").json()["rows"]
    assert {row[0]: row[1] for row in rows[1:]}["adapters_active"] == 0
