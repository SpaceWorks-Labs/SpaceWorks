from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.backup.models import BackupArchive
from apps.operations import reports
from apps.operations.models_report_schedules import ReportDelivery, ReportSchedule
from apps.operations.org_reports import organization_report_data
from apps.operations.report_registry import REPORT_REGISTRY
from apps.operations.platform_scope import _platform_context_for_view
from apps.accounts.models import User
from apps.operations.report_scope import combined_report_scope
from apps.organizations.models import Organization, OrganizationInvitation, OrganizationMakerspace, OrganizationMembership
from apps.makerspaces.models import Makerspace
from tests.operations.report_assertions import assert_report_disclosure_safe
from tests.return_helpers import authenticated_client, make_member, make_space, make_user

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("grain", ["day", "week", "month"])
def test_owner_org_funnel_scopes_and_deduplicates_repeated_owner_links(grain):
    a, b, foreign = make_space("j-org-a"), make_space("j-org-b"), make_space("j-org-foreign")
    org = Organization.objects.create(name="Owner", slug="j-org")
    other = Organization.objects.create(name="Other", slug="j-other-org")
    for space in (a, b):
        OrganizationMakerspace.objects.create(organization=org, makerspace=space, relationship="owner")
    OrganizationMakerspace.objects.create(organization=other, makerspace=foreign, relationship="owner")
    user = make_user("j-org-person")
    OrganizationMembership.objects.create(organization=org, user=user)
    OrganizationInvitation.objects.create(organization=org, token_digest="a" * 64, expires_at=timezone.now() + timedelta(days=1))
    OrganizationInvitation.objects.create(organization=other, token_digest="b" * 64, expires_at=timezone.now() + timedelta(days=1))
    local = reports.report_data("organization-membership", a.pk, grain=grain)
    assert all(r["organization_id"] == org.pk for r in local["typed_rows"])
    scope = combined_report_scope(Makerspace.objects.filter(pk__in=[a.pk, b.pk]))
    data = organization_report_data(REPORT_REGISTRY["organization-membership"], scope, limit=100, grain=grain)
    assert len(data["breakdown"]) == 2
    assert sum(r["invitations"] for r in data["total"]["rows"]) == 1
    assert sum(r["active_memberships"] for r in data["total"]["rows"]) == 1
    assert_report_disclosure_safe(data)
    superadmin = make_user("j-org-superadmin", role=User.Role.SUPERADMIN, access_status=User.AccessStatus.ACTIVE)
    aggregate = reports.report_data("organization-membership", grain=grain,
                                    platform_context=_platform_context_for_view(SimpleNamespace(user=superadmin)))
    assert all(r["makerspace_id"] in {a.pk, b.pk, foreign.pk} for r in aggregate["typed_rows"])
    assert_report_disclosure_safe(aggregate)


@pytest.mark.parametrize("grain", ["day", "week", "month"])
def test_delivery_health_uses_delivery_rows_scoped_to_each_tenant(grain):
    space, other = make_space("j-deliveries"), make_space("j-deliveries-other")
    actor = make_member("j-deliveries-actor", space)
    for tenant, statuses in ((space, ["sent", "failed"]), (other, ["sent", "sent", "sent"])):
        schedule = ReportSchedule.objects.create(makerspace=tenant, report_key="audit-activity", next_run_at=timezone.now(), created_by=actor)
        for status in statuses:
            ReportDelivery.objects.create(schedule=schedule, status=status, error="private response")
    data = reports.report_data("module-operational-health", space.pk, grain=grain)
    deliveries = [r for r in data["typed_rows"] if r["delivery_kind"] == "report_delivery"]
    assert len(deliveries) == 1
    delivery = deliveries[0]
    assert delivery["delivery_count"] == 2 and delivery["failure_count"] == 1
    assert delivery["success_rate_percent"] == 50
    assert "makerspace_id" not in delivery
    assert_report_disclosure_safe(data)


def test_backups_are_not_a_module_health_row_and_health_needs_authority():
    # P1b (#111 Q2): backup is a platform duty, not a module, so it never reports here.
    space = make_space("j-backup-health")
    BackupArchive.objects.create(makerspace=space, scope="makerspace", status="failed", object_key="j-health-private")
    data = reports.report_data("module-operational-health", space.pk)
    assert not [r for r in data["typed_rows"] if r["delivery_kind"] == "archive"]
    actor = make_member("j-health-member", space, membership_role="inventory_manager")
    response = authenticated_client(actor).get(f"/api/v1/admin/makerspace/{space.pk}/analytics/module-operational-health")
    assert response.status_code == 403
    assert_report_disclosure_safe(data)


def test_organization_membership_is_not_a_tenant_report_or_schedule():
    space = make_space("j-org-boundary")
    actor = make_member("j-org-boundary-actor", space)
    client = authenticated_client(actor)
    assert client.get(f"/api/v1/admin/makerspace/{space.pk}/analytics/organization-membership").status_code == 404
    catalog = client.get(f"/api/v1/admin/makerspace/{space.pk}/reports/catalog")
    assert "organization-membership" not in {r["key"] for r in catalog.data["results"]}
    assert not REPORT_REGISTRY["organization-membership"].schedulable


def test_ownerless_organization_still_has_its_own_authorized_funnel():
    actor = make_user("j-ownerless-actor", access_status=User.AccessStatus.ACTIVE)
    org = Organization.objects.create(name="Before tenants", slug="j-ownerless")
    OrganizationMembership.objects.create(organization=org, user=actor, granted_actions=["manage_makerspace"])
    response = authenticated_client(actor).get(f"/api/v1/admin/organizations/{org.pk}/analytics/organization-membership")
    assert response.status_code == 200, response.data
    assert response.data["breakdown"] == []
    assert sum(r["memberships"] for r in response.data["total"]["rows"]) == 1
    assert_report_disclosure_safe(response.data)
    stranger = make_user("j-ownerless-stranger", access_status=User.AccessStatus.ACTIVE)
    assert authenticated_client(stranger).get(f"/api/v1/admin/organizations/{org.pk}/analytics/organization-membership").status_code == 404
