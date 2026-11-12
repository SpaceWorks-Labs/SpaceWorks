import csv
from io import StringIO, BytesIO

import pytest
from openpyxl import load_workbook
from rest_framework.exceptions import PermissionDenied

from apps.accounts import rbac
from apps.operations import reports
from apps.operations.org_report_scope import EXCLUDED_ORGANIZATION_REPORT_KEYS
from apps.operations.org_report_strategies import STRATEGIES
from apps.operations.report_condition_metrics import NUMERIC_FIELDS
from apps.operations.report_registry import report_definition, ReportNotFound
from apps.operations.report_validation import validate_report_definition
from tests.operations.report_assertions import assert_report_disclosure_safe
from tests.fixed_roles.helpers import assign_builtin_roles, staff_account
from tests.return_helpers import authenticated_client, make_user
from .de_helpers_m1f2 import KEYS, BOOKING_KEYS, setup, seed

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("key", KEYS)
def test_definition_contract(key):
    definition = report_definition(key)
    validate_report_definition(definition)
    identity = key == "booking-top-members"
    assert definition.identity_bearing is identity
    assert definition.deployment_aggregate is not identity
    assert definition.schedulable is not identity
    assert definition.required_modules == (("bookings",) if key in BOOKING_KEYS else ("events",))
    assert definition.required_action == (rbac.Action.MANAGE_BOOKINGS if key in BOOKING_KEYS else rbac.Action.MANAGE_EVENTS)
    assert definition.grains == (() if identity else ("day", "week", "month"))
    assert definition.chart_spec is not None
    if key in {"booking-occupancy", "booking-lead-time", "booking-top-members", "event-checkin-times"}:
        assert key in EXCLUDED_ORGANIZATION_REPORT_KEYS
    else:
        strategy = STRATEGIES[key]
        assert set(strategy.total_fields) | set(strategy.breakdown_only_fields) == set(definition.fields) - {"makerspace_id"}
    if not identity:
        assert any(value["field"] in NUMERIC_FIELDS for value in definition.chart_spec["values"])


@pytest.mark.parametrize("key", KEYS)
def test_scope_modules_actions_and_disclosure(key):
    space, actor = setup(f"de-contract-{key}")
    foreign, outsider = setup(f"de-foreign-{key}")
    own_event, _ = seed(space, actor)
    foreign_event, _ = seed(foreign, outsider)
    definition = report_definition(key)
    response = reports.report_data(key, space.pk, actor=actor)
    assert response["typed_rows"]
    for row in response["typed_rows"]:
        assert set(row) <= set(definition.fields)
        if key not in BOOKING_KEYS:
            assert row["event_id"] == own_event.pk and row["event_id"] != foreign_event.pk
        if key == "booking-top-members":
            assert row["member_id"] in (actor.pk, None)
    if key == "booking-lead-time":
        assert sum(row["booking_count"] for row in response["typed_rows"]) == 1
    if key == "booking-occupancy":
        assert sum(float(row["occupied_hours"]) for row in response["typed_rows"]) == 1
    assert_report_disclosure_safe(response)
    assert foreign.pk not in {row.get("makerspace_id") for row in response["typed_rows"]}
    if definition.deployment_aggregate:
        aggregate = reports.report_data(key)
        assert {space.pk, foreign.pk} <= {row["makerspace_id"] for row in aggregate["typed_rows"]}
        assert_report_disclosure_safe(aggregate)
    else:
        with pytest.raises(ReportNotFound):
            reports.report_data(key)
        with pytest.raises(PermissionDenied):
            reports.report_data(key, space.pk, actor=outsider)
    url = f"/api/v1/admin/makerspace/{space.pk}/analytics/{key}"
    member = make_user(f"de-reader-{key}", access_status="active")
    assign_builtin_roles(member, space, "member")
    assert authenticated_client(member).get(url).status_code in (403, 404)
    assert authenticated_client(outsider).get(url).status_code in (403, 404)
    assert authenticated_client(actor).get(url).status_code == 200
    module = definition.required_modules[0]
    space.enabled_modules = [m for m in space.enabled_modules if m != module]
    space.save(update_fields=["enabled_modules"])
    # 0.12.0: a booking report also sits behind its `bookings.*` capability, so with the module off it is
    # a hidden surface (404) rather than a refused module (400).
    assert authenticated_client(actor).get(url).status_code in (400, 404)
    assert reports.report_data(key, space.pk, actor=actor)["typed_rows"] == []


@pytest.mark.parametrize("key", KEYS)
@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
def test_exports_are_allowlisted_and_disclosure_safe(key, fmt):
    space, actor = setup(f"de-export-{key}-{fmt}")
    seed(space, actor)
    response = authenticated_client(actor).get(
        f"/api/v1/admin/makerspace/{space.pk}/reports/{key}/export?format={fmt}")
    assert response.status_code == 200
    data = b"".join(response.streaming_content) if response.streaming else response.content
    if fmt == "csv":
        decoded = list(csv.reader(StringIO(data.decode().split("\n", 1)[1])))
    else:
        decoded = list(load_workbook(BytesIO(data), read_only=True).worksheets[0].values)
    assert set(decoded[0]) <= set(report_definition(key).fields)
    assert_report_disclosure_safe(decoded)


def test_booking_manager_reads_own_area_rankings_without_audit_authority(monkeypatch):
    # Decision 242(h): named rows for an area manager's own area do not need view_audit.
    space, actor = setup("de-ranking-authority")
    seed(space, actor)
    original = rbac.can
    monkeypatch.setattr(rbac, "can", lambda who, action, resource=None: False if action == rbac.Action.VIEW_AUDIT else original(who, action, resource))
    assert reports.report_data("booking-top-members", space.pk, actor=actor)["typed_rows"] is not None
    assert reports.report_rows("booking-top-members", space.pk, actor=actor) is not None
    response = authenticated_client(actor).get(f"/api/v1/admin/makerspace/{space.pk}/reports/catalog")
    assert response.status_code == 200
    assert "booking-top-members" in str(response.data)
    # Without the area action itself the ranking stays closed.
    monkeypatch.setattr(rbac, "can", lambda who, action, resource=None: False if action in (rbac.Action.VIEW_AUDIT, rbac.Action.MANAGE_BOOKINGS) else original(who, action, resource))
    with pytest.raises(PermissionDenied):
        reports.report_data("booking-top-members", space.pk, actor=actor)


@pytest.mark.parametrize("slug,admitted", [("booking_manager", BOOKING_KEYS[:-1]),
                                          ("event_manager", tuple(k for k in KEYS if k not in BOOKING_KEYS)),
                                          ("machine_manager", ())])
def test_domain_roles_do_not_borrow_another_actions_analytics(slug, admitted):
    space, manager = setup(f"de-role-{slug}")
    seed(space, manager)
    actor = staff_account(space, f"de-role-reader-{slug}", slug)
    client = authenticated_client(actor)
    for key in KEYS:
        response = client.get(f"/api/v1/admin/makerspace/{space.pk}/analytics/{key}")
        assert response.status_code == 200 if key in admitted else response.status_code in (403, 404)


def test_identity_ranking_cannot_be_scheduled_or_combined():
    from types import SimpleNamespace
    from rest_framework.exceptions import ValidationError
    from apps.operations.serializers_report_schedules import ReportScheduleSerializer
    from apps.operations.org_report_scope import resolve_organization_report_scope, UnsupportedOrganizationReport
    from apps.organizations.models import Organization
    space, actor = setup("de-ranking-schedule")
    serializer = ReportScheduleSerializer(context={"makerspace": space, "request": SimpleNamespace(user=actor)})
    with pytest.raises(ValidationError):
        serializer.validate({"report_key": "booking-top-members", "format": "csv", "grain": "day"})
    organization = Organization.objects.create(name="D E owner", slug="de-ranking-owner")
    with pytest.raises(UnsupportedOrganizationReport):
        resolve_organization_report_scope(actor, organization, report_definition("booking-top-members"))


@pytest.mark.parametrize("key", tuple(k for k in KEYS if k != "booking-top-members"))
def test_deployment_excludes_archived_and_reports_disabled_spaces(key):
    from django.utils import timezone
    visible, manager = setup(f"de-visible-{key}")
    seed(visible, manager)
    excluded = []
    for suffix in ("archived", "disabled"):
        space, actor = setup(f"de-{suffix}-{key}")
        seed(space, actor)
        if suffix == "archived":
            space.archived_at = timezone.now()
            space.save(update_fields=["archived_at"])
        else:
            space.enabled_modules = [m for m in space.enabled_modules if m != "reports"]
            space.save(update_fields=["enabled_modules"])
        excluded.append(space.pk)
    payload = reports.report_data(key)
    ids = {row["makerspace_id"] for row in payload["typed_rows"]}
    assert visible.pk in ids and not ids.intersection(excluded)
    assert_report_disclosure_safe(payload)
