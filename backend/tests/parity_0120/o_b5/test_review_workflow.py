"""O-B5: organization review workflow (written for the release gate; not run by the lane)."""
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.organizations import services_review
from apps.organizations.models import Organization, OrganizationMakerspace, OrganizationReview
from apps.organizations.services_console import OrganizationConflict, change_link
from apps.organizations.services_invitations import create_invitation
from apps.organizations.services_self_service import create_self_service

pytestmark = pytest.mark.django_db


def account(name="applicant"):
    actor = User.objects.create_user(username=name, email=f"{name}@example.test")
    User.objects.filter(pk=actor.pk).update(email_verified_at=timezone.now())
    actor.refresh_from_db()
    return actor


def superadmin():
    return User.objects.create_superuser(
        username="root", email="root@example.test", password="x" * 20,
        account_kind=User.AccountKind.PLATFORM, role=User.Role.SUPERADMIN,
        access_status=User.AccessStatus.ACTIVE,
    )


@pytest.fixture
def pending(settings):
    settings.ORGANIZATION_SELF_CREATION_ENABLED = True
    settings.ORGANIZATION_REVIEW_REQUIRED = True
    actor = account()
    return actor, create_self_service(actor, name="Guild", slug="guild")


def test_review_off_leaves_new_orgs_approved(settings):
    settings.ORGANIZATION_SELF_CREATION_ENABLED = True
    row = create_self_service(account(), name="Guild", slug="guild")
    assert row.review_status == "approved"
    assert not OrganizationReview.objects.exists()


def test_pending_org_is_inert(pending):
    actor, org = pending
    org.refresh_from_db()
    assert org.review_status == "pending_review"
    Organization.objects.filter(pk=org.pk).update(public_profile_enabled=True)
    response = APIClient().get(reverse("public-organization-detail", kwargs={"slug": org.slug}))
    assert response.status_code == 404
    with pytest.raises(OrganizationConflict):
        create_invitation(org, actor=actor, governance_actions=[], granted_actions=[])
    assert AuditLog.objects.filter(action="organization.review_submitted", actor=actor).count() == 1


def test_pending_org_takes_no_link(pending):
    from apps.makerspaces.models import Makerspace
    _, org = pending
    space = Makerspace.objects.create(name="Space", slug="space")
    with pytest.raises(OrganizationConflict):
        change_link(superadmin(), org.pk, space.pk, relationship="affiliate")
    assert not OrganizationMakerspace.objects.exists()


def test_only_superadmin_decides(pending):
    actor, org = pending
    with pytest.raises(PermissionDenied):
        services_review.decide(org, actor, "approve")


def test_approve_opens_and_history_is_append_only(pending):
    _, org = pending
    services_review.decide(org, superadmin(), "approve")
    org.refresh_from_db()
    assert org.review_status == "approved"
    entry = OrganizationReview.objects.filter(organization=org, action="approved").get()
    with pytest.raises(RuntimeError):
        entry.delete()
    entry.reason = "x"
    with pytest.raises(RuntimeError):
        entry.save()


def test_changes_requested_then_resubmit(pending):
    actor, org = pending
    root = superadmin()
    with pytest.raises(Exception):
        services_review.decide(org, root, "request_changes")  # a reason is required
    services_review.decide(org, root, "request_changes", "Add a website")
    org.refresh_from_db()
    assert org.review_status == "changes_requested"
    services_review.resubmit(org, actor, "Added")
    org.refresh_from_db()
    assert org.review_status == "pending_review"


def test_declined_slug_is_held_30_days_then_released(pending, settings):
    actor, org = pending
    services_review.decide(org, superadmin(), "decline", "Not a fit")
    org.refresh_from_db()
    assert not org.is_active
    other = account("other")
    with pytest.raises(OrganizationConflict):
        create_self_service(other, name="Guild 2", slug="guild")
    OrganizationReview.objects.filter(organization=org, action="declined").update(
        created_at=timezone.now() - timedelta(days=31))
    row = create_self_service(other, name="Guild 2", slug="guild")
    assert row.pk != org.pk and not Organization.objects.filter(pk=org.pk).exists()


def test_suspend_keeps_org_active_but_hides_it(pending):
    _, org = pending
    root = superadmin()
    services_review.decide(org, root, "approve")
    services_review.decide(org, root, "suspend", "Complaint")
    org.refresh_from_db()
    assert org.is_active and org.review_status == "suspended"
    services_review.decide(org, root, "reactivate")
    org.refresh_from_db()
    assert org.review_status == "approved"


def test_queue_route_is_superadmin_only(pending):
    actor, _ = pending
    client = APIClient()
    client.force_authenticate(actor)
    assert client.get(reverse("admin-organization-review-queue")).status_code == 403
    client.force_authenticate(superadmin())
    response = client.get(reverse("admin-organization-review-queue"))
    assert response.status_code == 200 and response.json()["count"] == 1
