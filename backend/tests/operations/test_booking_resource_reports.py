from datetime import datetime, timedelta, timezone as dt_timezone
from types import SimpleNamespace

import pytest
from django.http import Http404
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.bookings.models import BookableSpace
from apps.makerspaces.guards import SurfaceOff
from apps.operations import reports
from apps.operations.report_registry import REPORT_REGISTRY, report_definition, ReportNotFound
from apps.operations.report_subjects import SubjectFilterSerializer
from apps.operations.serializers_report_schedules import ReportScheduleSerializer
from apps.operations.views_report_views import authorize_view
from tests.operations.booking_report_helpers import KEYS, auditor, booking, client_for, filters, fixture, period

pytestmark = pytest.mark.django_db


def test_builder_parity_clipping_and_resource_tenant_predicate():
    tenant, actor, _, resource, *_ = fixture()
    start = datetime(2026, 10, 1, tzinfo=dt_timezone.utc)
    end = start + timedelta(hours=10)
    booking(resource, starts_at=start - timedelta(hours=1), ends_at=start + timedelta(hours=2), status="completed")
    booking(resource, starts_at=start + timedelta(hours=8), ends_at=end + timedelta(hours=2), status="no_show")
    booking(resource, starts_at=start - timedelta(hours=2), ends_at=start)  # exact boundary excluded
    booking(resource, starts_at=end, ends_at=end + timedelta(hours=2))
    other = BookableSpace.objects.create(makerspace=tenant, name="Other resource")
    booking(other, starts_at=start, ends_at=end)
    foreign, _, _, foreign_resource, *_ = fixture("foreign-report")
    booking(foreign_resource, starts_at=start, ends_at=end)
    legacy = reports.report_data("booking-utilization", tenant.pk, date_range=(start, end))["typed_rows"]
    result = reports.report_data("booking-resource-utilization", tenant.pk, actor=actor,
        report_filters=filters(resource), date_range=(start, end))
    row = result["typed_rows"][0]
    legacy_row, = [r for r in legacy if r["space_id"] == resource.pk]
    # The subject export retains its whole-window overlap counts; v2 analytics now
    # buckets outcomes by scheduled start. Elapsed clipped hours still agree.
    for field in ("space_id", "space_name", "reserved_hours", "completed_hours", "window_hours", "reservation_utilization_percent"):
        assert row[field] == legacy_row[field]
    assert "period" in legacy_row and "period" not in row
    assert row["arrived_reservations"] == row["confirmed_without_recorded_arrival"] == 0
    assert (row["reserved_hours"], row["completed_hours"], row["window_hours"]) == ("4.00", "2.00", "10.00")
    assert row["reservation_utilization_percent"] == 40.0
    assert row["no_show_rate_percent"] == 50.0
    assert result["meta"]["arrival_counts_available"] is True
    from apps.operations.reports_bookings import build_booking_utilization
    assert not build_booking_utilization(foreign.pk, **filters(resource)).records
    for bounds in (None, (start, None), (None, end)):
        row = reports.report_data("booking-resource-utilization", tenant.pk, actor=actor,
            report_filters=filters(resource), date_range=bounds)["typed_rows"][0]
        assert row["window_hours"] is None and row["reservation_utilization_percent"] is None


@pytest.mark.parametrize("key", KEYS)
def test_manager_preview_export_and_saved_authority(key):
    tenant, manager, _, resource, *_ = fixture()
    booking(resource)
    args = dict(actor=manager, report_filters=filters(resource), date_range=(timezone.now(), timezone.now() + timedelta(days=3)))
    assert reports.report_data(key, tenant.pk, **args)["typed_rows"]
    assert reports.report_rows(key, tenant.pk, **args)[1:]
    assert authorize_view(manager, tenant, {"report_key": key, "filters": period(resource)}).key == key


@pytest.mark.parametrize("key", ("booking-utilization", "booking-resource-utilization", "booking-reservations", "booking-answers"))
def test_grant_and_tenant_audit_conjunction_on_every_disclosure(key):
    tenant, _, grantee, resource, grant, _ = fixture()
    booking(resource)
    state = {"report_key": key, "filters": filters(resource)}
    for run in (reports.report_data, reports.report_rows):
        with pytest.raises(PermissionDenied):
            run(key, tenant.pk, actor=grantee, report_filters=filters(resource))
    with pytest.raises(PermissionDenied):
        authorize_view(grantee, tenant, state)
    membership = auditor(tenant, grantee)
    client = client_for(grantee)
    for route in ("analytics-generic", "report-export"):
        response = client.get(reverse(route, args=[tenant.pk, key]), filters(resource))
        assert response.status_code == 200, getattr(response, "data", None)
    assert authorize_view(grantee, tenant, state).key == key
    sibling = BookableSpace.objects.create(makerspace=tenant, name="Not delegated")
    with pytest.raises(PermissionDenied):
        reports.report_data(key, tenant.pk, actor=grantee, report_filters=filters(sibling))
    foreign, _, _, foreign_resource, *_ = fixture("foreign-grant-report")
    with pytest.raises(Http404):
        reports.report_data(key, tenant.pk, actor=grantee, report_filters=filters(foreign_resource))
    grant.revoked_at = timezone.now(); grant.save(update_fields=["revoked_at"])
    for route in ("analytics-generic", "report-export"):
        assert client.get(reverse(route, args=[tenant.pk, key]), filters(resource)).status_code == 403
    with pytest.raises(PermissionDenied):
        authorize_view(grantee, tenant, state)


@pytest.mark.parametrize("permission", ["edit_details", "check_in", "publish_page"])
def test_auditor_with_wrong_resource_permission_cannot_read(permission):
    tenant, _, grantee, resource, grant, _ = fixture()
    auditor(tenant, grantee)
    grant.permissions = [permission]; grant.save(update_fields=["permissions"])
    for key in KEYS:
        with pytest.raises(PermissionDenied):
            reports.report_data(key, tenant.pk, actor=grantee, report_filters=filters(resource))


@pytest.mark.parametrize("payload", [{"subject_kind": "bookable_space"}, {"subject_id": 1},
    {"subject_kind": "bookable_space", "subject_id": 0}, {"subject_kind": "missing", "subject_id": 1}])
def test_typed_subject_boundary(payload):
    assert not SubjectFilterSerializer(data=payload).is_valid()


def test_features_modules_and_legacy_permissions_are_independent():
    tenant, manager, grantee, resource, *_ = fixture()
    auditor(tenant, grantee)
    for feature, keys in [("bookings.analytics", ("booking-utilization", "booking-resource-utilization", "booking-resource-utilization-pdf")),
        ("bookings.exports", ("booking-reservations", "booking-answers")), ("bookings.utilization_pdf", ("booking-resource-utilization-pdf",))]:
        original = tenant.enabled_features[:]
        tenant.enabled_features.remove(feature); tenant.save(update_fields=["enabled_features"])
        for key in keys:
            # Decision 183B gap 12: an off feature is a typed 404 (SurfaceOff), not a 400.
            with pytest.raises((ValidationError, SurfaceOff)):
                reports.report_data(key, tenant.pk, actor=manager, report_filters=filters(resource))
        # The established tenant-wide report remains available to an auditor alone.
        assert reports.report_data("booking-utilization", tenant.pk, actor=grantee)["typed_rows"]
        tenant.enabled_features = original; tenant.save(update_fields=["enabled_features"])
    for module in ("reports", "bookings"):
        original = tenant.enabled_modules[:]
        tenant.enabled_modules.remove(module); tenant.save(update_fields=["enabled_modules"])
        for key in KEYS:
            with pytest.raises((ValidationError, SurfaceOff)):
                reports.report_rows(key, tenant.pk, actor=manager, report_filters=filters(resource))
        tenant.enabled_modules = original; tenant.save(update_fields=["enabled_modules"])


def test_pdf_requires_full_manager_and_complete_positive_period():
    tenant, manager, grantee, resource, *_ = fixture()
    auditor(tenant, grantee)
    key = "booking-resource-utilization-pdf"
    valid = (timezone.now(), timezone.now() + timedelta(days=1))
    with pytest.raises(PermissionDenied):
        reports.report_rows(key, tenant.pk, actor=grantee, report_filters=filters(resource), date_range=valid)
    for bounds in (None, (valid[0], None), (None, valid[1]), (valid[0], valid[0]), tuple(reversed(valid))):
        with pytest.raises(ValidationError):
            reports.report_rows(key, tenant.pk, actor=manager, report_filters=filters(resource), date_range=bounds)
    assert reports.report_rows(key, tenant.pk, actor=manager, report_filters=filters(resource), date_range=valid)[1:]


def test_new_reports_and_all_subject_filters_refuse_aggregate_schedule_and_org():
    tenant, manager, _, resource, *_ = fixture()
    from apps.operations.org_report_scope import EXCLUDED_ORGANIZATION_REPORT_KEYS
    from apps.operations.report_schedule_services import _skip_reason
    for key in KEYS:
        definition = REPORT_REGISTRY[key]
        assert not definition.schedulable and not definition.deployment_aggregate
        assert key in EXCLUDED_ORGANIZATION_REPORT_KEYS
        with pytest.raises(ReportNotFound):
            report_definition(key, deployment_aggregate=True)
        # Since 1f-0 a non-aggregate key without a makerspace is refused as not found
        # before authorization runs; either refusal keeps the aggregate path closed.
        with pytest.raises((PermissionDenied, ReportNotFound)):
            reports.report_rows(key, actor=manager, report_filters=filters(resource))
    for key in (*KEYS, "booking-utilization"):
        payload = {"report_key": key, "filters": filters(resource), "recipient_emails": ["external@example.test"]}
        serializer = ReportScheduleSerializer(data=payload, context={"makerspace": tenant, "request": SimpleNamespace(user=manager)})
        assert not serializer.is_valid()
    assert _skip_reason(SimpleNamespace(filters=filters(resource)), REPORT_REGISTRY["booking-utilization"]) == "subject_filter_not_schedulable"
    client = client_for(manager)
    for url in ("/api/v1/admin/analytics/booking-utilization", "/api/v1/admin/reports/booking-utilization/export",
                "/api/v1/admin/organizations/1/analytics/booking-utilization"):
        assert client.get(url, filters(resource)).status_code == 400


@pytest.mark.parametrize("state", ["inactive", "restricted", "suspended", "stub", "archived"])
def test_live_account_and_tenant_restrictions(state):
    tenant, _, user, resource, _, _ = fixture()
    auditor(tenant, user)
    if state == "inactive":
        user.is_active = False; user.save(update_fields=["is_active"])
    elif state in ("restricted", "suspended"):
        user.access_status = state; user.save(update_fields=["access_status"])
    elif state == "stub":
        user.is_tenant_dump_stub = True; user.save(update_fields=["is_tenant_dump_stub"])
    else:
        tenant.archived_at = timezone.now(); tenant.save(update_fields=["archived_at"])
    for key in KEYS:
        with pytest.raises(PermissionDenied):
            reports.report_data(key, tenant.pk, actor=user, report_filters=filters(resource))


def test_organization_actions_reach_tenant_reports_without_local_identity():
    from apps.accounts.models import User
    from apps.organizations.models import Organization, OrganizationMakerspace, OrganizationMembership
    from apps.operations.org_report_scope import UnsupportedOrganizationReport, resolve_organization_report_scope
    tenant, _, _, resource, *_ = fixture()
    org = Organization.objects.create(name="Booking organization", slug="booking-report-org")
    OrganizationMakerspace.objects.create(organization=org, makerspace=tenant, relationship="owner")
    actor = User.objects.create_user(username="booking-org-auditor", access_status="active")
    membership = OrganizationMembership.objects.create(organization=org, user=actor,
        granted_actions=["manage_bookings", "view_audit"])
    booking(resource)
    assert not actor.makerspace_memberships.exists()
    for key in KEYS:
        result = reports.report_data(key, tenant.pk, actor=actor, report_filters=filters(resource),
            date_range=(timezone.now(), timezone.now() + timedelta(days=3)))
        assert result["typed_rows"]
        with pytest.raises(UnsupportedOrganizationReport):
            resolve_organization_report_scope(actor, org, REPORT_REGISTRY[key])
    membership.granted_actions = ["view_audit"]; membership.save(update_fields=["granted_actions"])
    with pytest.raises(PermissionDenied):
        reports.report_data("booking-resource-utilization", tenant.pk, actor=actor, report_filters=filters(resource))


def test_feature_projection_has_no_scanner_contact_or_pdf_escalation():
    tenant, manager, user, resource, grant, _ = fixture()
    auditor(tenant, user)
    url = reverse("admin-bookable-space-detail", args=[resource.pk])
    manager_data = client_for(manager).get(url)
    assert manager_data.status_code == 200, manager_data.data
    assert manager_data.data["report_features"] == ["analytics", "exports", "pdf"]
    assert client_for(user).get(url).data["report_features"] == ["analytics", "exports"]
    grant.permissions = ["check_in"]; grant.save(update_fields=["permissions"])
    assert client_for(user).get(url).data["report_features"] == []


def test_installer_picks_up_booking_features_only_with_reports():
    from apps.makerspaces.capabilities import FEATURES, default_enabled_features
    from apps.makerspaces.setup_areas import features_for
    from tests.operations.booking_report_helpers import FEATURES as keys
    assert set(keys) <= set(features_for(["bookings", "reports"]))
    assert not set(keys) & set(features_for(["bookings"]))
    assert not set(keys) & set(default_enabled_features())
    for key in keys:
        assert FEATURES[key].parent_module == "bookings"
        assert "reports" in FEATURES[key].requires_modules
