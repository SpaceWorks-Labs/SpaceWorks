import csv
from io import BytesIO, StringIO

import pytest
from django.urls import reverse
from openpyxl import load_workbook

from apps.accounts import rbac
from apps.accounts.models import User
from apps.accounts.models_activity import DeviceActivityDay
from apps.audit.services import record
from apps.integrations.models import EmailLog
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.operations.org_report_aggregate import aggregate_rows
from apps.operations.org_report_scope import EXCLUDED_ORGANIZATION_REPORT_KEYS
from apps.operations.org_report_strategies import STRATEGIES
from apps.operations.org_reports import organization_report_data
from apps.operations.report_condition_metrics import condition_metrics
from apps.operations.report_coverage import REPORT_MODULE_COVERAGE
from apps.operations.report_exports import csv_bytes, xlsx_bytes
from apps.operations.report_exports_provenance import build_provenance
from apps.operations.report_registry import report_definition
from apps.operations.report_scope import combined_report_scope
from apps.operations.report_validation import validate_report_definition
from apps.operations.reports import report_data, report_rows
from tests.operations.report_assertions import assert_report_disclosure_safe
from tests.return_helpers import authenticated_client, make_member, make_space
from tests.test_native_push import device_client, push_member

KEYS = ("communications-health", "mobile-devices", "mobile-auth")


@pytest.mark.parametrize("key", KEYS)
def test_count_only_definitions_charts_conditions_and_organization_contract(key):
    definition = report_definition(key)
    validate_report_definition(definition)
    assert not definition.identity_bearing and not definition.platform_only
    assert definition.deployment_aggregate and definition.schedulable
    assert definition.required_action == rbac.Action.MANAGE_MAKERSPACE
    assert definition.grains == ("day", "week", "month")
    assert "makerspace_id" in definition.fields
    assert definition.chart_spec["partition"] == "tenant"
    assert definition.chart_spec["truncation"] is None
    assert definition.chart_spec["x"] == {"field": "period", "kind": "time"}
    assert key in STRATEGIES and key not in EXCLUDED_ORGANIZATION_REPORT_KEYS
    assert set(STRATEGIES[key].total_fields) | set(STRATEGIES[key].breakdown_only_fields) == set(definition.fields) - {"makerspace_id"}
    assert condition_metrics(definition)
    if key != "communications-health":
        assert definition.required_modules == ("mobile",)
        assert key in REPORT_MODULE_COVERAGE["mobile"].reports
    else:
        assert definition.version == 4  # lane R: rebuilt on canonical delivery records
        assert {"inbox_read_count", "invalid_count", "bounced_count", "read_rate_percent"} <= set(condition_metrics(definition))


@pytest.mark.django_db
@pytest.mark.parametrize("key", KEYS)
def test_manager_can_read_but_other_roles_and_tenants_cannot(key):
    space, other = make_space("hi-role"), make_space("hi-role-other")
    manager = make_member("hi-role-manager", space)
    url = reverse("analytics-generic", args=[space.pk, key])
    response = authenticated_client(manager).get(url + "?grain=week")
    assert response.status_code == 200, response.data
    assert_report_disclosure_safe(response.data)
    assert authenticated_client(manager).get(reverse("analytics-generic", args=[other.pk, key])).status_code in (403, 404)
    for role in (MakerspaceMembership.Role.INVENTORY_MANAGER, MakerspaceMembership.Role.MACHINE_MANAGER,
                 MakerspaceMembership.Role.HANDOVER, MakerspaceMembership.Role.EVENT_MANAGER):
        actor = make_member(f"hi-role-{role}", space, membership_role=role, role=User.Role.REQUESTER)
        assert authenticated_client(actor).get(url).status_code in (403, 404)
    # H/I has no machine source; a machine-type assignment cannot grant space
    # administration or expose another member's auth/delivery telemetry.


@pytest.mark.django_db
@pytest.mark.parametrize("key", ("mobile-devices", "mobile-auth"))
def test_mobile_module_is_enforced_on_builder_catalog_and_http(key):
    space = make_space("hi-module")
    manager = make_member("hi-module-manager", space)
    space.enabled_modules.remove("mobile")
    space.save(update_fields=["enabled_modules"])
    client = authenticated_client(manager)
    response = client.get(reverse("analytics-generic", args=[space.pk, key]))
    assert response.status_code == 404, response.data
    assert report_definition(key).builder()(space.pk).records == []
    catalog = client.get(reverse("report-catalog", args=[space.pk]))
    assert catalog.status_code == 200
    # #183B: a report whose source module is off is hidden from the catalogue.
    assert key not in {r["key"] for r in catalog.data["results"]}


@pytest.mark.django_db
@pytest.mark.parametrize("key", KEYS)
def test_aggregate_rows_preserve_tenant_ids(key):
    first, second = make_space("hi-agg-a"), make_space("hi-agg-b")
    for space in (first, second):
        user = push_member(f"hi-agg-user-{space.pk}", space)
        if key == "communications-health":
            EmailLog.objects.create(makerspace=space, to_email="private@example.com", subject="secret message", status="sent")
        elif key == "mobile-auth":
            record(None, "auth.device_login_succeeded", makerspace=space, meta={"platform": "apple"})
        else:
            _, grant = device_client(user, space)
            from datetime import date
            DeviceActivityDay.objects.create(grant=grant, makerspace=space, platform="apple", local_day=date(2026, 10, 12))
    rows = report_definition(key).builder()(None).records
    assert {row["makerspace_id"] for row in rows} == {first.pk, second.pk}
    assert_report_disclosure_safe(rows)
    scoped = report_definition(key).builder()(first.pk).records
    assert all("makerspace_id" not in row for row in scoped)


@pytest.mark.django_db
@pytest.mark.parametrize("key", KEYS)
def test_preview_csv_xlsx_and_organization_obey_exact_allowlist(key):
    space = make_space("hi-disclosure")
    user = push_member("hi-disclosure-user", space)
    EmailLog.objects.create(makerspace=space, to_email="private@example.com", subject="secret message",
                             status="sent", text_body="private body", source_metadata={"token": "private"})
    _, grant = device_client(user, space)
    from datetime import date
    DeviceActivityDay.objects.create(grant=grant, makerspace=space, platform="apple", local_day=date(2026, 10, 12))
    record(None, "auth.device_login_failed", makerspace=space,
           meta={"reason": "invalid_credentials", "token": "private", "platform": "apple"})
    definition = report_definition(key)
    preview = report_data(key, space.pk, grain="week")
    assert_report_disclosure_safe(preview)
    rows = report_rows(key, space.pk, grain="week")
    assert set(rows[0]) == set(definition.fields) - {"makerspace_id"}
    assert len(rows) > 1
    provenance = build_provenance(key, version=definition.version, makerspace_id=space.pk,
                                  generated_by="test", filters={"grain": "week"})
    decoded_csv = list(csv.reader(StringIO(csv_bytes(rows, provenance=provenance).decode().split("\n", 1)[1])))
    assert decoded_csv[0] == list(rows[0])
    assert_report_disclosure_safe(decoded_csv)
    workbook = load_workbook(BytesIO(xlsx_bytes(rows, provenance=provenance)), read_only=True)
    decoded_xlsx = list(workbook["Report"].values)
    assert decoded_xlsx[0] == tuple(rows[0])
    assert_report_disclosure_safe(decoded_xlsx)
    scope = combined_report_scope(Makerspace.objects.filter(pk=space.pk))
    payload = organization_report_data(definition, scope, limit=100, grain="week")
    assert payload["total"]["rows"]
    assert_report_disclosure_safe(payload)


@pytest.mark.parametrize("key,dimensions", [
    ("mobile-devices", dict(metric="grants", platform="apple", environment="production", authority="staff", status="active")),
    ("mobile-auth", dict(metric="device_logins", platform="apple", environment="production", outcome="failed", reason="unknown")),
])
def test_mobile_organization_sums_match_dimensions_and_preserve_periods(key, dimensions):
    row = {"period": "2026-10-12", "count": 2, **dimensions}
    other = {**row, "platform": "android", "count": 5}
    later = {**row, "period": "2026-10-19", "count": 7}
    rows = aggregate_rows(key, [(1, [row]), (2, [row, other, later])], limit=100)
    assert len(rows) == 3
    assert next(r["count"] for r in rows if r["period"] == row["period"] and r["platform"] == "apple") == 4
    assert_report_disclosure_safe(rows)
