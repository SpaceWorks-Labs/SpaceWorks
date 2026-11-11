"""The six deferred authorization races (a4fa9084): a grant revoked AFTER the view's
unlocked authorization but BEFORE the service's write must refuse the write.

Each test wraps the service entry point the view calls so the revocation commits in the
gap the real race exploits, then asserts a 403 and that nothing was written.
"""

import pytest
from django.test import override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.accounts.rbac import Action
from apps.audit.models import AuditLog
from apps.machines import service_workflow
from apps.machines.models import Machine, MachineOperator, MachineServiceRequest, MachineType, ServiceBucket
from apps.machines.models_membership_scope import MembershipMachineTypeScope
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.warranty import services as warranty_services
from apps.warranty import views as warranty_views
from apps.warranty.models import Warranty, WarrantyDocument
from tests.account_split_g2_helpers import staff_for_actions
from tests.return_helpers import authenticated_client, make_member, make_space, make_user
from tests.test_warranty import (
    attach_asset_warranty,
    make_asset,
    make_machine,
    mock_warranty_storage,
    warranty_payload,
)

pytestmark = pytest.mark.django_db


def _revoke(user, space):
    MakerspaceMembership.objects.filter(user=user, makerspace=space).update(status="revoked")


def _revoking(monkeypatch, target, name, revoke):
    original = getattr(target, name)

    def wrapped(*args, **kwargs):
        revoke()
        return original(*args, **kwargs)

    monkeypatch.setattr(target, name, wrapped)


@override_settings(PLATFORM_DOMAIN_SUFFIX="")
def test_domain_verification_refuses_when_manager_is_revoked_after_lookup(monkeypatch):
    from apps.admin_api import views_domain_verification

    space = make_space("race-domain")
    space.frontend_domain = "race-domain.example"
    space.save(update_fields=["frontend_domain"])
    # Self-host trusts a new domain on save; start from PENDING so a write would show.
    Makerspace.objects.filter(pk=space.pk).update(
        frontend_domain_status=Makerspace.DomainStatus.PENDING, domain_verified_at=None,
    )
    manager = make_member("race-domain-manager", space)
    _revoking(monkeypatch, views_domain_verification, "verify_domain", lambda: _revoke(manager, space))

    response = authenticated_client(manager).post(
        reverse("makerspace-verify-domain", kwargs={"makerspace_id": space.pk}), HTTP_HOST="localhost",
    )

    space.refresh_from_db()
    assert response.status_code == 403
    assert space.frontend_domain_status == Makerspace.DomainStatus.PENDING
    assert not AuditLog.objects.filter(action="makerspace.domain_verify_attempt").exists()


@override_settings(PLATFORM_DOMAIN_SUFFIX="")
def test_domain_verification_still_verifies_for_a_live_manager():
    space = make_space("race-domain-ok")
    space.frontend_domain = "race-domain-ok.example"
    space.save(update_fields=["frontend_domain"])
    manager = make_member("race-domain-ok-manager", space)

    response = authenticated_client(manager).post(
        reverse("makerspace-verify-domain", kwargs={"makerspace_id": space.pk}), HTTP_HOST="localhost",
    )

    assert response.status_code == 200, response.data
    assert response.data["status"] == Makerspace.DomainStatus.VERIFIED


def _completed_laser_job(slug):
    space = make_space(slug)
    laser = MachineType.objects.create(makerspace=space, slug=f"{slug}-laser", name="Laser")
    machine = Machine.objects.create(makerspace=space, machine_type=laser, name="Laser")
    bucket, _ = ServiceBucket.objects.get_or_create(machine=machine, name="Race")
    requester = make_user(f"{slug}-requester", access_status=User.AccessStatus.ACTIVE)
    row = MachineServiceRequest.objects.create(
        makerspace=space, bucket=bucket, assigned_machine=machine, requester=requester,
        requester_name=requester.username, title="Job", status=MachineServiceRequest.Status.COMPLETED,
    )
    actor, membership = staff_for_actions(space, f"{slug}-actor", [Action.MANAGE_MACHINES], machine_types=[laser])
    return space, row, actor, membership


def _collect(actor, row):
    return authenticated_client(actor).post(
        reverse("admin-machine-service-request-collect", args=[row.pk]), {}, format="json",
    )


def test_collect_refuses_when_membership_is_revoked_after_lookup(monkeypatch):
    space, row, actor, _ = _completed_laser_job("race-collect-member")
    _revoking(monkeypatch, service_workflow, "collect", lambda: _revoke(actor, space))

    response = _collect(actor, row)

    row.refresh_from_db()
    assert response.status_code == 403
    assert row.status == MachineServiceRequest.Status.COMPLETED


def test_collect_refuses_when_machine_scope_is_narrowed_after_lookup(monkeypatch):
    space, row, actor, membership = _completed_laser_job("race-collect-scope")
    _revoking(
        monkeypatch, service_workflow, "collect",
        lambda: MembershipMachineTypeScope.objects.filter(membership=membership).delete(),
    )

    response = _collect(actor, row)

    row.refresh_from_db()
    assert response.status_code == 403
    assert row.status == MachineServiceRequest.Status.COMPLETED


def test_collect_still_succeeds_for_an_in_scope_actor():
    _, row, actor, _ = _completed_laser_job("race-collect-ok")

    response = _collect(actor, row)

    row.refresh_from_db()
    assert response.status_code == 200, response.data
    assert row.status == MachineServiceRequest.Status.COLLECTED


def test_asset_warranty_put_refuses_when_manager_is_revoked_after_lookup(monkeypatch):
    space = make_space("race-asset-warranty")
    asset = make_asset(space)
    manager = make_member("race-asset-warranty-manager", space)
    _revoking(monkeypatch, warranty_views, "upsert_warranty", lambda: _revoke(manager, space))

    response = authenticated_client(manager).put(
        reverse("admin-asset-warranty", kwargs={"pk": asset.pk}), warranty_payload(), format="json",
    )

    assert response.status_code == 403
    assert not Warranty.objects.filter(asset=asset).exists()


def test_machine_warranty_put_refuses_when_operator_row_is_removed_after_lookup(monkeypatch):
    space = make_space("race-machine-warranty")
    machine = make_machine(space)
    operator = make_member(
        "race-machine-warranty-operator", space,
        membership_role=MakerspaceMembership.Role.CUSTOM, role=User.Role.REQUESTER,
    )
    MachineOperator.objects.create(machine=machine, user=operator, access_level=MachineOperator.AccessLevel.MANAGE)
    client = authenticated_client(operator)
    url = reverse("admin-machine-warranty", kwargs={"pk": machine.pk})
    assert client.get(url).status_code == 200
    _revoking(
        monkeypatch, warranty_views, "upsert_warranty",
        lambda: MachineOperator.objects.filter(machine=machine, user=operator).delete(),
    )

    response = client.put(url, warranty_payload(), format="json")

    assert response.status_code == 403
    assert not Warranty.objects.filter(machine=machine).exists()


def _document_case(monkeypatch, slug):
    mock_warranty_storage(monkeypatch)
    space = make_space(slug)
    warranty = attach_asset_warranty(make_asset(space))
    manager = make_member(f"{slug}-manager", space)
    return space, warranty, manager, authenticated_client(manager)


def test_document_presign_refuses_when_manager_is_revoked_after_lookup(monkeypatch):
    space, warranty, manager, client = _document_case(monkeypatch, "race-doc-presign")
    _revoking(monkeypatch, warranty_services, "presign_document", lambda: _revoke(manager, space))

    response = client.post(
        reverse("admin-warranty-document-presign", kwargs={"pk": warranty.pk}),
        {"filename": "bill.pdf", "content_type": "application/pdf"}, format="json",
    )

    assert response.status_code == 403
    assert "upload" not in (response.data or {})


def test_document_finalize_refuses_when_manager_is_revoked_after_lookup(monkeypatch):
    space, warranty, manager, client = _document_case(monkeypatch, "race-doc-finalize")
    _revoking(monkeypatch, warranty_services, "finalize_document", lambda: _revoke(manager, space))

    response = client.post(
        reverse("admin-warranty-documents", kwargs={"pk": warranty.pk}),
        {"object_key": f"warranty/{space.pk}/race.pdf", "original_filename": "race.pdf"}, format="json",
    )

    assert response.status_code == 403
    assert not WarrantyDocument.objects.exists()
    assert not AuditLog.objects.filter(action="warranty.document_added").exists()


def test_document_delete_refuses_when_manager_is_revoked_after_lookup(monkeypatch):
    space, warranty, manager, client = _document_case(monkeypatch, "race-doc-delete")
    document = WarrantyDocument.objects.create(
        warranty=warranty, object_key=f"warranty/{space.pk}/kept.pdf", original_filename="kept.pdf",
        content_type="application/pdf", size_bytes=1, uploaded_by=manager,
    )
    _revoking(monkeypatch, warranty_services, "delete_document", lambda: _revoke(manager, space))

    response = client.delete(reverse("admin-warranty-document-detail", kwargs={"pk": document.pk}))

    assert response.status_code == 403
    assert WarrantyDocument.objects.filter(pk=document.pk).exists()
    assert not AuditLog.objects.filter(action="warranty.document_removed").exists()


def test_document_lifecycle_still_works_for_a_live_manager(monkeypatch, django_capture_on_commit_callbacks):
    space, warranty, _, client = _document_case(monkeypatch, "race-doc-ok")
    presign = client.post(
        reverse("admin-warranty-document-presign", kwargs={"pk": warranty.pk}),
        {"filename": "bill.pdf", "content_type": "application/pdf"}, format="json",
    )
    assert presign.status_code == 201, presign.data
    finalized = client.post(
        reverse("admin-warranty-documents", kwargs={"pk": warranty.pk}),
        {"object_key": presign.data["object_key"], "original_filename": "bill.pdf"}, format="json",
    )
    assert finalized.status_code == 201, finalized.data
    with django_capture_on_commit_callbacks(execute=True):
        deleted = client.delete(reverse("admin-warranty-document-detail", kwargs={"pk": finalized.data["id"]}))
    assert deleted.status_code == 204
    assert not WarrantyDocument.objects.exists()
