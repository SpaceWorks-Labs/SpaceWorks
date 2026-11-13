from datetime import timedelta

import pytest
from django.core import mail
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.hosting_requests.models import HostingRequest
from apps.makerspaces.models import Makerspace
from apps.organizations import governance
from tests.hosting_requests.helpers import (
    ANSWER, RESOLVE, anonymous, client_for, invited_row, member_governor, org_member,
    owned_space, payload, space, space_manager,
)

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("managed")]
PRIVATE = {"applicant_email", "applicant_name", "applicant_phone", "description", "rejection_reason"}


def ms_url(makerspace, pk=None):
    base = f"/api/v1/admin/makerspaces/{makerspace.pk}/hosting-invitations"
    return base if pk is None else f"{base}/{pk}/cancel"


def org_url(organization, pk=None):
    base = f"/api/v1/admin/organizations/{organization.pk}/hosting-invitations/"
    return base if pk is None else f"{base}{pk}/cancel"


def invite(client, url, email="invitee@example.test", **extra):
    return client.post(url, {"invitee_email": email, "space_name": "New Lab", **extra}, format="json")


def token_from(response):
    return response.data["invite_url"].split("#token=")[1]


def test_space_manager_invites_with_own_organization_only():
    makerspace, _owner = owned_space("staff-inviter")
    manager = space_manager(makerspace)
    response = invite(client_for(manager), ms_url(makerspace), note="Come build with us")

    assert response.status_code == 201, response.data
    assert response.data["join_offered"] is False
    assert response.data["invite_url"].startswith("https://app.space-works.test/hosting/invite#token=")
    assert response.data["delivery_status"] == "sent"
    assert response["Cache-Control"] == "no-store"
    row = HostingRequest.objects.get()
    assert row.inviter_organization_id is None and row.organization_choice == "own"
    assert row.invite_token_digest != token_from(response)
    assert mail.outbox[-1].to == ["invitee@example.test"] and "Come build with us" in mail.outbox[-1].body
    entry = AuditLog.objects.get(action="hosting_request.invitation_created")
    assert entry.meta["inviter_organization_id"] is None
    assert entry.meta["inviter_makerspace_id"] == makerspace.pk

    preview = anonymous().post(RESOLVE, {"token": token_from(response)}, format="json")
    assert preview.status_code == 200 and preview.data["join_organization_name"] is None
    answer = anonymous().post(ANSWER, {**payload(), "token": token_from(response),
                                       "organization_choice": "join"}, format="json")
    assert answer.status_code == 400 and "organization_choice" in answer.data


def test_member_governor_gets_join_pre_selected(django_capture_on_commit_callbacks):
    makerspace, owner = owned_space("governor-inviter", org_name="Riverside Org")
    governor = member_governor(owner)
    response = invite(client_for(governor), ms_url(makerspace))
    assert response.status_code == 201, response.data
    assert response.data["join_offered"] is True
    token = token_from(response)
    preview = anonymous().post(RESOLVE, {"token": token}, format="json")
    assert preview.data["join_organization_name"] == "Riverside Org"
    assert preview.data["inviter_name"] == makerspace.name
    with django_capture_on_commit_callbacks(execute=True):
        answer = anonymous().post(ANSWER, {**payload(), "token": token, "organization_choice": "join"},
                                  format="json")
    assert answer.status_code == 202
    row = HostingRequest.objects.get()
    assert row.status == "pending_verification" and row.organization_choice == "join"
    assert row.new_organization_name == "" and row.applicant_email == "ada@example.test"
    assert "/hosting/request#token=" in mail.outbox[-1].body


def test_staff_without_manage_makerspace_is_refused():
    makerspace = space("weak-staff")
    from tests.accounts.account_factories import make_staff

    clerk = make_staff(makerspace, username="weak-clerk", role_slug="inventory_manager",
                       email="weak-clerk@example.test", access_status="active")
    assert invite(client_for(clerk), ms_url(makerspace)).status_code == 403
    assert client_for(clerk).get(ms_url(makerspace)).status_code == 403


def test_other_tenant_staff_and_archived_spaces_are_refused():
    mine, other = space("tenant-mine"), space("tenant-other")
    manager = space_manager(mine)
    assert invite(client_for(manager), ms_url(other)).status_code in (403, 404)
    archived = space("tenant-archived", archived_at=timezone.now())
    archived_manager = space_manager(archived)
    assert invite(client_for(archived_manager), ms_url(archived)).status_code == 404


def test_tenant_origin_scopes_makerspace_routes_and_refuses_organization_routes():
    makerspace = space("origin-own", frontend_domain="own.example.test",
                       frontend_domain_status=Makerspace.DomainStatus.VERIFIED)
    other = space("origin-other")
    manager = space_manager(makerspace)
    origin = {"HTTP_ORIGIN": "https://own.example.test"}
    client = client_for(manager)
    created = client.post(ms_url(makerspace), {"invitee_email": "a@example.test"}, format="json", **origin)
    assert created.status_code == 201, created.data
    assert client.get(ms_url(makerspace), **origin).status_code == 200
    assert client.post(ms_url(makerspace, created.data["id"]), format="json", **origin).status_code == 200
    assert client.get(ms_url(other), **origin).status_code == 404  # 481(1): no standing there, as if missing

    org_space, organization = owned_space("origin-org")
    governor = member_governor(organization, "origin-governor")
    refused = client_for(governor).get(org_url(organization), **origin)
    assert refused.status_code == 403


def test_organization_invite_needs_member_governance():
    _space, organization = owned_space("org-invites", org_name="Guild")
    governor = org_member(organization, "guild-governor",
                          governance_actions=[governance.MANAGE_ORGANIZATION_MEMBERS])
    profile_only = org_member(organization, "guild-profile",
                              governance_actions=[governance.MANAGE_ORGANIZATION_PROFILE])
    assert invite(client_for(profile_only), org_url(organization)).status_code == 403
    response = invite(client_for(governor), org_url(organization))
    assert response.status_code == 201 and response.data["join_offered"] is True
    listing = client_for(governor).get(org_url(organization))
    assert listing.status_code == 200 and listing.data["count"] == 1
    assert not PRIVATE & set(listing.data["results"][0])
    preview = anonymous().post(RESOLVE, {"token": token_from(response)}, format="json")
    assert preview.data["inviter_name"] == "Guild" and preview.data["join_organization_name"] == "Guild"


def test_expired_invitation_is_404_and_resubmit_rotates_the_access_token():
    makerspace = space("expiry")
    row, raw = invited_row(makerspace=makerspace, invite_expires_at=timezone.now() - timedelta(minutes=1))
    assert anonymous().post(RESOLVE, {"token": raw}, format="json").status_code == 404
    assert anonymous().post(ANSWER, {**payload(), "token": raw}, format="json").status_code == 404

    live, live_raw = invited_row(makerspace=makerspace)
    assert anonymous().post(ANSWER, {**payload(), "token": live_raw}, format="json").status_code == 202
    live.refresh_from_db()
    first_digest = live.access_token_digest
    assert anonymous().post(ANSWER, {**payload(applicant_email="new@example.test"), "token": live_raw},
                            format="json").status_code == 202
    live.refresh_from_db()
    assert live.access_token_digest != first_digest and live.applicant_email == "new@example.test"
    assert live.status == "pending_verification"


def test_cancel_scope_and_state_rules():
    makerspace, other = space("cancel-home"), space("cancel-away")
    manager = space_manager(makerspace)
    row, _ = invited_row(makerspace=makerspace, invited_by=manager)
    client = client_for(manager)
    # A matching id under another scope is invisible.
    other_row, _ = invited_row(makerspace=other)
    assert client.post(ms_url(makerspace, other_row.pk), format="json").status_code == 404
    cancelled = client.post(ms_url(makerspace, row.pk), format="json")
    assert cancelled.status_code == 200 and cancelled.data["status"] == "withdrawn"
    assert AuditLog.objects.filter(action="hosting_request.invitation_cancelled").count() == 1
    submitted, _ = invited_row(makerspace=makerspace, status="submitted")
    conflict = client.post(ms_url(makerspace, submitted.pk), format="json")
    assert conflict.status_code == 409 and conflict.data["code"] == "invalid_transition"


def test_listing_exposes_no_applicant_details_and_marks_expiry():
    makerspace = space("listing")
    manager = space_manager(makerspace)
    invited_row(makerspace=makerspace, applicant_name="Secret Name",
                invite_expires_at=timezone.now() - timedelta(days=1))
    response = client_for(manager).get(ms_url(makerspace))
    assert response.status_code == 200
    item = response.data["results"][0]
    assert not PRIVATE & set(item) and "Secret Name" not in str(response.data)
    assert item["display_status"] == "expired"
