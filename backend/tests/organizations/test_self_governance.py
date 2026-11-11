import pytest
from django.urls import reverse
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient

from apps.accounts import rbac
from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.makerspaces.models import Makerspace
from apps.organizations import governance
from apps.organizations.models import Organization, OrganizationMembership, OrganizationMakerspace
from apps.organizations.services_console import OrganizationConflict
from apps.organizations.services_governance import delete_organization, update_membership

pytestmark = pytest.mark.django_db


def setup_governed():
    org = Organization.objects.create(name="Governed", slug="governed")
    actor = User.objects.create_user(username="governor")
    member = OrganizationMembership.objects.create(organization=org, user=actor,
        governance_actions=sorted(governance.GOVERNANCE_ACTIONS))
    return org, actor, member


@pytest.mark.parametrize("changes", [{"status": "suspended"}, {"governance_actions": []}])
def test_last_governor_cannot_be_removed(changes):
    org, actor, member = setup_governed()
    with pytest.raises(OrganizationConflict):
        update_membership(org, member.pk, actor=actor, **changes)
    member.refresh_from_db()
    assert member.status == "active"
    assert governance.MANAGE_ORGANIZATION_MEMBERS in member.governance_actions
    assert not AuditLog.objects.filter(action="organization.membership_updated").exists()


def test_another_governor_allows_transfer_but_cannot_escalate():
    org, actor, member = setup_governed()
    successor = User.objects.create_user(username="successor")
    other = OrganizationMembership.objects.create(organization=org, user=successor)
    changed = update_membership(org, other.pk, actor=actor,
                                governance_actions=sorted(governance.GOVERNANCE_ACTIONS))
    assert set(changed.governance_actions) == governance.GOVERNANCE_ACTIONS
    update_membership(org, member.pk, actor=actor, governance_actions=[])
    with pytest.raises(PermissionDenied):
        update_membership(org, other.pk, actor=successor,
                          granted_actions=[rbac.Action.MANAGE_MAKERSPACE])


def test_suspended_grants_cannot_be_reactivated_by_weaker_governor():
    org, actor, _ = setup_governed()
    target = OrganizationMembership.objects.create(organization=org,
        user=User.objects.create_user(username="suspended"), status="suspended",
        granted_actions=[rbac.Action.MANAGE_EVENTS])
    with pytest.raises(PermissionDenied):
        update_membership(org, target.pk, actor=actor, status="active")
    target.refresh_from_db()
    assert target.status == "suspended"


def test_other_organization_membership_is_not_mutable():
    from django.http import Http404
    org, actor, _ = setup_governed()
    other = Organization.objects.create(name="Foreign", slug="foreign")
    target = OrganizationMembership.objects.create(organization=other, user=actor)
    with pytest.raises(Http404):
        update_membership(org, target.pk, actor=actor, status="suspended")


def test_safe_delete_refuses_linked_spaces_and_keeps_history():
    org, actor, _ = setup_governed()
    space = Makerspace.objects.create(name="Linked", slug="linked")
    link = OrganizationMakerspace.objects.create(organization=org, makerspace=space, relationship="owner")
    with pytest.raises(OrganizationConflict):
        delete_organization(org, actor=actor)
    assert Organization.objects.filter(pk=org.pk).exists()
    link.delete()
    org_id = org.pk
    delete_organization(org, actor=actor)
    assert not Organization.objects.filter(pk=org_id).exists()
    assert AuditLog.objects.filter(action="organization.deleted", target_id=str(org_id)).exists()
    assert Makerspace.objects.filter(pk=space.pk).exists()


def test_event_references_and_artwork_refuse_delete():
    from datetime import timedelta
    from django.utils import timezone
    from apps.events.models import Event, EventOrganizer
    org, actor, _ = setup_governed()
    space = Makerspace.objects.create(name="Host", slug="host")
    event = Event.objects.create(makerspace=space, title="History", starts_at=timezone.now(),
                                 ends_at=timezone.now() + timedelta(hours=1))
    EventOrganizer.objects.create(event=event, organization=org)
    with pytest.raises(OrganizationConflict):
        delete_organization(org, actor=actor)
    assert EventOrganizer.objects.filter(event=event, organization=org).exists()
    EventOrganizer.objects.filter(event=event).delete()
    org.logo_key = "organizations/private-artwork.webp"
    org.save(update_fields=["logo_key"])
    with pytest.raises(OrganizationConflict):
        delete_organization(org, actor=actor)


def test_delete_requires_both_governance_actions():
    org, actor, member = setup_governed()
    member.governance_actions = [governance.MANAGE_ORGANIZATION_MEMBERS]
    member.save(update_fields=["governance_actions"])
    with pytest.raises(PermissionDenied):
        delete_organization(org, actor=actor)


def test_sensitive_http_mutations_require_recent_reauth():
    org, actor, member = setup_governed()
    client = APIClient()
    client.force_authenticate(actor)
    urls = [
        ("delete", reverse("admin-organization-detail", kwargs={"pk": org.pk}), {}),
        ("patch", reverse("admin-organization-membership-detail", kwargs={"pk": org.pk, "membership_id": member.pk}), {"status": "suspended"}),
        ("post", reverse("admin-organization-invitations", kwargs={"pk": org.pk}), {"governance_actions": []}),
    ]
    for method, url, payload in urls:
        response = getattr(client, method)(url, payload, format="json")
        assert response.status_code == 403
    assert Organization.objects.filter(pk=org.pk).exists()


def test_self_service_organization_is_global_not_a_tenant_purge_subject():
    from apps.data_export.classification import MODELS
    from apps.data_export.types import GlobalReference
    org, _, _ = setup_governed()
    assert not any(field.name == "makerspace" for field in org._meta.fields)
    assert isinstance(MODELS["organizations.Organization"], GlobalReference)


def test_http_governance_positive_and_foreign_organization_refusal(monkeypatch):
    monkeypatch.setattr("apps.accounts.reauthentication.require_recent_reauth", lambda request: None)
    monkeypatch.setattr("apps.organizations.views_governance.require_recent_reauth", lambda request: None)
    org, actor, _ = setup_governed()
    target = OrganizationMembership.objects.create(organization=org,
        user=User.objects.create_user(username="target"))
    client = APIClient()
    client.force_authenticate(actor)
    url = reverse("admin-organization-membership-detail", kwargs={"pk": org.pk, "membership_id": target.pk})
    assert client.patch(url, {"status": "suspended"}, format="json").status_code == 200
    foreign = Organization.objects.create(name="Foreign", slug="foreign")
    other_url = reverse("admin-organization-detail", kwargs={"pk": foreign.pk})
    assert client.delete(other_url).status_code == 404
    assert client.delete(reverse("admin-organization-detail", kwargs={"pk": org.pk})).status_code == 204
    assert Organization.objects.filter(pk=foreign.pk).exists()
