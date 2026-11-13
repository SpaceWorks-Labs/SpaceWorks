"""The control-plane owner editor must use the same service as the console."""

import pytest
from django.contrib.admin import AdminSite
from django.test import RequestFactory
from rest_framework.exceptions import NotFound, PermissionDenied

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.events.organization_audience import OrganizationAudienceRefused, require_organization_audience
from apps.organizations.admin import OrganizationMakerspaceAdmin, OrganizationMakerspaceInline
from apps.organizations.models import Organization, OrganizationMakerspace
from apps.organizations.services_console import change_link
from tests.events.organization_audience_helpers import audience_fixture, local

pytestmark = pytest.mark.django_db(transaction=True)


def test_standalone_admin_owner_change_immediately_removes_local_membership_proof_and_audits():
    _, orgs, spaces, event, _ = audience_fixture()
    user = local(spaces[0])
    require_organization_audience(event, user)
    root = User.objects.create_superuser(username="owner-admin", password="pw")
    request = RequestFactory().post("/control/"); request.user = root
    row = OrganizationMakerspace.objects.get(organization=orgs[0], makerspace=spaces[0])
    row.relationship = "affiliate"
    admin = OrganizationMakerspaceAdmin(OrganizationMakerspace, AdminSite())
    admin.save_model(request, row, None, True)
    with pytest.raises(OrganizationAudienceRefused):
        require_organization_audience(event, user)
    entry = AuditLog.objects.get(action="organization.link_updated")
    assert entry.makerspace_id == spaces[0].pk
    assert entry.meta == {"organization_id": orgs[0].pk, "relationship": "affiliate"}
    assert "membership" not in str(entry.meta)


def test_owner_console_keeps_superadmin_write_gate():
    _, orgs, spaces, _, manager = audience_fixture()
    with pytest.raises(PermissionDenied):
        change_link(manager, orgs[0].pk, spaces[0].pk, relationship="affiliate")


def test_organization_inline_is_read_only_so_parent_first_writes_cannot_bypass_service():
    root = User.objects.create_superuser(username="inline-owner-admin", password="pw")
    request = RequestFactory().post("/control/"); request.user = root
    inline = OrganizationMakerspaceInline(Organization, AdminSite())
    assert not inline.has_add_permission(request)
    assert not inline.has_change_permission(request)
    assert not inline.has_delete_permission(request)
