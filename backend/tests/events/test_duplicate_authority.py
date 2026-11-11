"""A successful duplicate must remain manageable by the duplicating actor."""
from tests.events.manual_grant_fixture import create_manual_grant

from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.events import event_authority
from apps.events.event_permissions import EDIT_DETAILS, PERMISSIONS
from apps.events.models import Event, EventOrganizer, EventStaffGrant
from apps.events.serializers_event_details import EventAdminSerializer
from apps.events.services_clone import duplicate_event
from apps.makerspaces.models import Makerspace
from apps.organizations.models import Organization, OrganizationMembership
from tests.fixed_roles.helpers import assign_builtin_roles

pytestmark = pytest.mark.django_db


def setup_event(*, staff=False):
    tenant = Makerspace.objects.create(
        name="Clone venue", slug="clone-venue", enabled_modules=["events"],
    )
    actor = User.objects.create_user(username="clone-actor", access_status="active",
        **({"account_kind": "staff", "staff_makerspace": tenant} if staff else {}))
    start = timezone.now() + timedelta(days=1)
    event = Event.objects.create(
        makerspace=tenant, title="Original", starts_at=start,
        ends_at=start + timedelta(hours=2), status=Event.Status.PUBLISHED,
    )
    client = APIClient()
    client.force_authenticate(actor)
    return tenant, actor, event, client


@pytest.mark.parametrize("permissions", [[EDIT_DETAILS], list(PERMISSIONS)])
def test_scoped_editor_cannot_duplicate_even_with_every_resource_permission(permissions):
    tenant, actor, event, client = setup_event()
    create_manual_grant(
        makerspace=tenant, event=event, user=actor, permissions=permissions,
    )
    detail = client.get(reverse("admin-event-detail", args=[event.pk]))
    assert detail.status_code == 200, detail.data
    assert EDIT_DETAILS in detail.data["staff_permissions"]
    assert detail.data["can_duplicate"] is False
    listing = client.get(reverse("admin-accessible-events"))
    assert listing.status_code == 200, listing.data
    assert listing.data["results"][0]["can_duplicate"] is False
    before = AuditLog.objects.filter(action="event.duplicated").count()
    response = client.post(reverse("admin-event-duplicate", args=[event.pk]), {}, format="json")
    assert response.status_code == 403, response.data
    # The service also rejects callers that bypass the view.
    with pytest.raises(PermissionDenied):
        duplicate_event(event, actor=actor)
    assert Event.objects.count() == 1
    assert AuditLog.objects.filter(action="event.duplicated").count() == before


def test_event_organizer_without_tenant_authority_cannot_duplicate():
    tenant, actor, event, _client = setup_event()
    organization = Organization.objects.create(name="Event organizers", slug="event-organizers")
    OrganizationMembership.objects.create(
        organization=organization, user=actor, granted_actions=["manage_events"],
    )
    EventOrganizer.objects.create(event=event, organization=organization)
    data = EventAdminSerializer(event, context={"request": SimpleNamespace(user=actor)}).data
    assert data["can_manage_staff"] is True
    assert data["can_duplicate"] is False
    with pytest.raises(PermissionDenied):
        duplicate_event(event, actor=actor)
    assert Event.objects.filter(makerspace=tenant).count() == 1


def test_tenant_manager_can_duplicate_and_read_the_audited_draft():
    tenant, actor, event, client = setup_event(staff=True)
    assign_builtin_roles(actor, tenant, "event_manager")
    detail = client.get(reverse("admin-event-detail", args=[event.pk]))
    assert detail.status_code == 200, detail.data
    assert detail.data["can_duplicate"] is True
    listing = client.get(reverse("admin-event-list-create", args=[tenant.pk]))
    assert listing.status_code == 200, listing.data
    assert listing.data["results"][0]["can_duplicate"] is True
    response = client.post(reverse("admin-event-duplicate", args=[event.pk]), {}, format="json")
    assert response.status_code == 201, response.data
    clone = Event.objects.get(pk=response.data["id"])
    assert clone.status == Event.Status.DRAFT
    assert clone.created_by == actor
    assert clone.makerspace_id == tenant.pk
    assert event_authority.can_manage_grants(actor, clone)
    assert client.get(reverse("admin-event-detail", args=[clone.pk])).status_code == 200
    assert response.data["can_duplicate"] is True
    assert AuditLog.objects.filter(
        action="event.duplicated", makerspace=tenant, actor=actor,
        meta__source_event_id=event.pk,
    ).exists()


def test_duplicate_projection_rechecks_tenant_authority_on_each_response():
    tenant, actor, event, _client = setup_event(staff=True)
    membership = assign_builtin_roles(actor, tenant, "event_manager")
    context = {"request": SimpleNamespace(user=actor)}
    assert EventAdminSerializer(event, context=context).data["can_duplicate"] is True
    membership.status = "revoked"
    membership.save(update_fields=["status"])
    assert EventAdminSerializer(event, context={
        "request": SimpleNamespace(user=actor),
    }).data["can_duplicate"] is False
    with pytest.raises(PermissionDenied):
        duplicate_event(event, actor=actor)


def test_duplicate_projection_without_actor_fails_closed():
    _tenant, _actor, event, _client = setup_event()
    assert EventAdminSerializer(event).data["can_duplicate"] is False


def test_openapi_declares_duplicate_capability_as_read_only_boolean():
    from drf_spectacular.generators import SchemaGenerator

    schema = SchemaGenerator().get_schema(request=None, public=True)
    field = schema["components"]["schemas"]["EventAdmin"]["properties"]["can_duplicate"]
    assert field["type"] == "boolean"
    assert field["readOnly"] is True
