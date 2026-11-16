"""Picker through tenant data uses platform JWTs, without issuing tenant authority."""
import pytest
from rest_framework.test import APIClient

from apps.accounts import rbac
from apps.accounts.models import User
from apps.accounts.tokens import SpaceWorksRefreshToken
from tests.return_helpers import make_space, make_user, make_product, make_member

pytestmark = pytest.mark.django_db
ROOT = "/api/v1/admin/platform/analytics/makerspaces"


def bearer(user, settings):
    settings.PLATFORM_STAFF_ORIGINS = ["https://platform.example.test"]
    access = SpaceWorksRefreshToken.for_user(user).access_token
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}", HTTP_ORIGIN=settings.PLATFORM_STAFF_ORIGINS[0])
    return client


def platform(settings):
    return bearer(make_user("fg-platform", role=User.Role.SUPERADMIN), settings)


def test_platform_picker_to_catalog_charts_dashboard_and_export(settings):
    space = make_space("fg-picker")
    make_product(space, name="Selected tenant drill")
    other = make_space("fg-other")
    make_product(other, name="Foreign tenant saw")
    client = platform(settings)
    picker = client.get(ROOT)
    assert picker.status_code == 200, picker.data
    selected = next(row for row in picker.data["results"] if row["id"] == space.pk)
    base = f"{ROOT}/{selected['id']}"
    catalog = client.get(f"{base}/reports/catalog")
    assert catalog.status_code == 200, catalog.data
    assert "recently-added" in {row["key"] for row in catalog.data["results"]}
    report = client.get(f"{base}/analytics/summary")
    assert report.status_code == 200 and report.data["products"] == 1, report.data
    dashboard = client.get(f"{base}/dashboard")
    assert dashboard.status_code == 200 and "widgets" in dashboard.data, dashboard.data
    export = client.get(f"{base}/reports/recently-added/export?format=csv")
    assert export.status_code == 200
    assert b"Selected tenant drill" in export.content and b"Foreign tenant saw" not in export.content
    # Owner decision #115: the superadmin also reads the tenant staff surface itself.
    assert client.get(f"/api/v1/admin/makerspace/{space.pk}/reports/catalog").status_code == 200
    assert client.post(f"{base}/dashboard", {}, format="json").status_code == 405


@pytest.mark.parametrize("suffix", ["reports/catalog", "analytics/summary", "dashboard", "reports/recently-added/export?format=csv"])
def test_unservable_tenants_cannot_be_read_directly(settings, suffix):
    from django.utils import timezone
    space = make_space("fg-hidden")
    client = platform(settings)
    space.archived_at = timezone.now()
    space.save(update_fields=["archived_at"])
    assert space.pk not in {row["id"] for row in client.get(ROOT).data["results"]}
    assert client.get(f"{ROOT}/{space.pk}/{suffix}").status_code == 404


@pytest.mark.parametrize("suffix", ["reports/catalog", "analytics/summary", "dashboard", "reports/recently-added/export?format=csv"])
def test_member_and_tenant_staff_cannot_use_platform_tenant_routes(settings, suffix):
    space = make_space("fg-staff-boundary")
    for user in (make_user("fg-member"), make_member("fg-staff", space)):
        assert bearer(user, settings).get(f"{ROOT}/{space.pk}/{suffix}").status_code == 403


def test_platform_reads_preserve_report_rbac_and_module_gates(settings, monkeypatch):
    space = make_space("fg-report-actions")
    client = platform(settings)
    base = f"{ROOT}/{space.pk}"
    from apps.operations.report_registry import REPORT_REGISTRY
    original = rbac.can
    # Deny each report's OWN registered action (recently-added is a legacy report
    # gated by its definition's required_action, not by inventory scope).
    denied = {rbac.Action.VIEW_INVENTORY, REPORT_REGISTRY["summary"].required_action,
              REPORT_REGISTRY["recently-added"].required_action}
    monkeypatch.setattr(rbac, "can", lambda actor, action, resource=None:
                        False if action in denied else original(actor, action, resource))
    assert client.get(f"{base}/analytics/summary").status_code == 403
    assert client.get(f"{base}/reports/recently-added/export?format=csv").status_code == 403
    catalog = client.get(f"{base}/reports/catalog")
    assert catalog.status_code == 200
    assert "summary" not in {row["key"] for row in catalog.data["results"]}
    monkeypatch.setattr(rbac, "can", original)
    space.enabled_modules = [key for key in space.enabled_modules if key != "reports"]
    space.save(update_fields=["enabled_modules"])
    assert client.get(f"{base}/reports/catalog").status_code == 404
    assert client.get(f"{base}/analytics/summary").status_code == 404
    assert client.get(f"{base}/reports/recently-added/export?format=csv").status_code == 404


def test_platform_route_registry_resolves_tenant_without_granting_api_client_authority(settings):
    from django.urls import resolve
    from rest_framework.request import Request
    from rest_framework.test import APIRequestFactory
    from apps.accounts.delegated_routes import PLATFORM_ONLY, route_class
    from apps.apiclients.scope_registry import lookup
    from apps.makerspaces.origin_scope_routes import request_route_targets
    for suffix in ("reports/catalog", "analytics/summary", "dashboard", "reports/recently-added/export"):
        path = f"{ROOT}/123/{suffix}"
        request = Request(APIRequestFactory().get(path))
        request.resolver_match = resolve(path)
        name, targets, invalid, recognized = request_route_targets(request)
        assert targets == {123} and recognized and not invalid
        assert route_class(name) == PLATFORM_ONLY
        assert lookup(request.resolver_match.view_name, "GET") is None


def test_platform_native_authority_remains_forbidden(settings):
    import uuid
    from apps.accounts.services_device_grants import authority_for_login, DeviceSuperadminNotSupported
    from apps.accounts.models import DeviceGrant
    user = make_user("fg-no-platform-device", role=User.Role.SUPERADMIN)
    space = make_space("fg-no-platform-device")
    with pytest.raises(DeviceSuperadminNotSupported):
        authority_for_login(user, login_method="password")
    settings.PLATFORM_STAFF_ORIGINS = ["https://platform.example.test"]
    token = SpaceWorksRefreshToken.for_user(user).access_token
    token["device_grant_id"] = str(uuid.uuid4())
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}", HTTP_ORIGIN=settings.PLATFORM_STAFF_ORIGINS[0])
    for suffix in ("reports/catalog", "analytics/summary", "dashboard", "reports/recently-added/export?format=csv"):
        assert client.get(f"{ROOT}/{space.pk}/{suffix}").status_code == 401
    assert not DeviceGrant.objects.filter(user=user).exists()
