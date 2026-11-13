from dataclasses import replace
from types import SimpleNamespace

import pytest
from rest_framework.exceptions import PermissionDenied

from apps.accounts.models import User
from apps.operations import org_reports, report_registry, reports, views_reports
from apps.operations.platform_scope import (
    PlatformContext, _platform_context_for_view, platform_analytics_spaces, require_platform_context,
)
from apps.operations.report_schedule_services import _skip_reason
from apps.operations.report_types import ReportDefinition, ReportNotFound, ReportResult
from apps.operations.serializers_report_schedules import ReportScheduleSerializer
from tests.return_helpers import authenticated_client, make_member, make_space, make_user


_PLATFORM_KEYS = tuple(key for key, definition in report_registry.REPORT_REGISTRY.items()
                       if definition.platform_only)


@pytest.fixture(params=_PLATFORM_KEYS or (None,), ids=lambda key: key or "synthetic-platform")
def platform_report(monkeypatch, request):
    # Once platform builders land, run the complete refusal matrix for EACH
    # registered key. Until then, exercise infrastructure with a test-only key.
    definition = report_registry.REPORT_REGISTRY[request.param] if request.param else ReportDefinition(
        "infra-platform", "unused.infra_platform", ("count",), platform_only=True,
        schedulable=False, allowed_formats=("csv", "xlsx", "pdf"),
    )
    monkeypatch.setitem(report_registry.REPORT_REGISTRY, definition.key, definition)
    monkeypatch.setattr(views_reports, "REPORT_DEFINITIONS", (*views_reports.REPORT_DEFINITIONS, definition))
    field = ReportScheduleSerializer._declared_fields["report_key"]
    monkeypatch.setattr(field, "choices", [*field.choices, definition.key])
    calls = []

    def builder(makerspace_id=None, *, platform_context=None, **kwargs):
        require_platform_context(platform_context)
        calls.append((makerspace_id, kwargs))
        return ReportResult(("count",), [{"count": 3}])

    monkeypatch.setattr("apps.operations.report_types.import_string", lambda _path: builder)
    return definition, calls


@pytest.mark.django_db
@pytest.mark.parametrize("path", [
    "analytics/{key}", "reports/{key}/export?format=csv",
    "reports/{key}/export?format=xlsx", "reports/{key}/export?format=pdf",
])
def test_platform_key_is_404_on_all_tenant_preview_and_export_paths(platform_report, path):
    space = make_space("infra-platform-tenant")
    actor = make_member("infra-platform-manager", space)
    response = authenticated_client(actor).get(
        f"/api/v1/admin/makerspace/{space.pk}/{path.format(key=platform_report[0].key)}"
    )
    assert response.status_code == 404, response.data
    assert not platform_report[1]


@pytest.mark.django_db
def test_tenant_catalog_omits_platform_keys(platform_report):
    space = make_space("infra-platform-catalog")
    actor = make_member("infra-platform-catalog-manager", space)
    response = authenticated_client(actor).get(f"/api/v1/admin/makerspace/{space.pk}/reports/catalog")
    assert response.status_code == 200, response.data
    assert platform_report[0].key not in {row["key"] for row in response.data["results"]}
    assert all({"chart_spec", "identity_bearing", "fields", "required_modules"} <= row.keys()
               for row in response.data["results"])


@pytest.mark.django_db
def test_organization_direct_access_refuses_platform_keys(platform_report):
    actor = make_user("infra-platform-org", access_status=User.AccessStatus.ACTIVE)
    response = authenticated_client(actor).get(
        f"/api/v1/admin/organizations/123/analytics/{platform_report[0].key}"
    )
    assert response.status_code == 404, response.data


def test_organization_enumeration_and_orchestration_refuse_platform_keys(platform_report):
    assert platform_report[0].key not in org_reports.organization_strategy_keys()
    with pytest.raises(ReportNotFound):
        org_reports.organization_report_data(platform_report[0], None, limit=10)
    assert not platform_report[1]


@pytest.mark.parametrize("runner", [reports.report_data, reports.report_rows])
@pytest.mark.parametrize("makerspace_id", [None, 123])
def test_platform_keys_cannot_be_called_through_generic_report_functions(platform_report, runner, makerspace_id):
    with pytest.raises(ReportNotFound):
        runner(platform_report[0].key, makerspace_id)
    assert not platform_report[1]


@pytest.mark.django_db
def test_schedule_creation_refuses_platform_key(platform_report):
    space = make_space("infra-platform-schedule")
    actor = make_member("infra-platform-schedule-manager", space)
    response = authenticated_client(actor).post(f"/api/v1/admin/makerspaces/{space.pk}/report-schedules", {
        "report_key": platform_report[0].key, "recipient_emails": ["external@example.test"],
    }, format="json")
    # Platform keys are never offered as schedule choices, so the serializer refuses them with
    # the standard 400 validation error; either refusal keeps the key unschedulable.
    assert response.status_code in (400, 404), response.data
    if response.status_code == 400:
        assert "report_key" in response.data


def test_schedule_eligibility_refuses_platform_key(platform_report):
    schedule = SimpleNamespace(filters={}, report_key=platform_report[0].key)
    assert _skip_reason(schedule, platform_report[0]) == "report_unavailable"
    # Explicit flag remains a guard even if a malformed future definition lies
    # about eligibility (system checks are an independent layer).
    assert _skip_reason(schedule, replace(platform_report[0], schedulable=True)) == "report_unavailable"


def test_context_is_protected_and_checked_again_at_each_use(platform_report):
    actor = User(username="infra-platform-admin", role=User.Role.SUPERADMIN,
                 access_status=User.AccessStatus.ACTIVE)
    with pytest.raises(TypeError):
        PlatformContext(actor)
    with pytest.raises(PermissionDenied):
        require_platform_context(SimpleNamespace(actor=actor))
    with pytest.raises(PermissionDenied):
        platform_report[0].builder()()
    ctx = _platform_context_for_view(SimpleNamespace(user=actor))
    definition = report_registry.report_definition(platform_report[0].key, platform_context=ctx)
    assert definition.builder()(platform_context=ctx).records == [{"count": 3}]
    actor.is_active = False
    with pytest.raises(PermissionDenied):
        require_platform_context(ctx)
    with pytest.raises(PermissionDenied):
        definition.builder()(platform_context=ctx)


def test_normal_staff_cannot_obtain_platform_context():
    actor = User(username="infra-platform-context-manager", role=User.Role.SPACE_MANAGER,
                 access_status=User.AccessStatus.ACTIVE)
    with pytest.raises(PermissionDenied):
        _platform_context_for_view(SimpleNamespace(user=actor))


@pytest.mark.django_db
@pytest.mark.parametrize("path", ["analytics/{key}", "reports/{key}/export?format=csv"])
def test_platform_superadmin_views_supply_builder_context(platform_report, path):
    actor = make_user("infra-platform-view-admin", role=User.Role.SUPERADMIN,
                      access_status=User.AccessStatus.ACTIVE)
    response = authenticated_client(actor).get(f"/api/v1/admin/{path.format(key=platform_report[0].key)}")
    assert response.status_code == 200, getattr(response, "data", None)
    assert len(platform_report[1]) == 1 and platform_report[1][0][0] is None


@pytest.mark.django_db
def test_platform_scope_covers_every_space_and_ignores_the_retired_access_flag():
    flagged = make_space("infra-flag-off")
    visible = make_space("infra-visible")
    actor = make_user("infra-platform-admin", role=User.Role.SUPERADMIN, access_status=User.AccessStatus.ACTIVE)
    ctx = _platform_context_for_view(SimpleNamespace(user=actor))
    assert {flagged.pk, visible.pk} <= set(platform_analytics_spaces(ctx).values_list("pk", flat=True))
    client = authenticated_client(actor)
    path = "/api/v1/admin/makerspace/{}/analytics/communications-health"
    assert client.get(path.format(flagged.pk)).status_code == client.get(path.format(visible.pk)).status_code
