"""#185 item 5: a public "host my space" request, superadmin approval, the space is created
and its Space Manager invited -- end to end, from the web console."""

import pytest
from django.core import mail

from apps.accounts.models import StaffInvitation
from apps.audit.models import AuditLog
from apps.hosting_requests.models import HostingRequest
from apps.makerspaces.models import Makerspace
from apps.organizations.models import OrganizationMakerspace
from tests.hosting_requests.helpers import OPEN, SUBMIT, anonymous, last_token, payload, public_row

from .helpers import api, superadmin

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("managed")]
BASE = "/api/v1/admin/platform/hosting-requests"


def test_public_request_to_running_space(django_capture_on_commit_callbacks):
    root = superadmin()
    with django_capture_on_commit_callbacks(execute=True):
        assert anonymous().post(SUBMIT, payload(expected_members=40), format="json").status_code == 202
    token = last_token()
    with django_capture_on_commit_callbacks(execute=True):
        assert anonymous().post(OPEN, {"token": token}, format="json").status_code == 200
    row = HostingRequest.objects.get()
    assert row.status == "submitted" and row.expected_members == 40

    listed = api(root).get(BASE, {"status": "submitted"}).json()
    assert listed["count"] == 1 and listed["results"][0]["expected_members"] == 40
    with django_capture_on_commit_callbacks(execute=True):
        response = api(root).post(f"{BASE}/{row.pk}/approve", {"invite_manager": True}, format="json")
    assert response.status_code == 200, response.content
    body = response.json()
    space = Makerspace.objects.get(pk=body["makerspace"]["id"])
    assert space.slug == "riverside" and body["request"]["status"] == "accepted"
    assert body["request"]["created_makerspace"]["id"] == space.pk
    assert OrganizationMakerspace.objects.filter(makerspace=space, relationship="owner").exists()
    assert "email" in space.enabled_modules
    invitation = StaffInvitation.objects.get(makerspace=space)
    assert invitation.role_snapshot == ["space_manager"] and invitation.email == "ada@example.test"
    assert any(message.to == ["ada@example.test"] and "Staff invitation" in message.subject
               for message in mail.outbox)
    assert AuditLog.objects.filter(action="space_control.space_onboarded", makerspace=space).exists()
    assert AuditLog.objects.filter(action="hosting_request.makerspace_linked").exists()


def test_approve_refuses_a_taken_slug_and_a_second_approval(django_capture_on_commit_callbacks):
    root = superadmin()
    Makerspace.objects.create(name="Taken", slug="taken")
    row, _ = public_row(proposed_slug="taken")
    assert api(root).post(f"{BASE}/{row.pk}/approve", {}, format="json").status_code == 400
    row.refresh_from_db()
    assert row.status == "submitted"  # rolled back with the failed creation
    with django_capture_on_commit_callbacks(execute=True):
        assert api(root).post(f"{BASE}/{row.pk}/approve", {"slug": "fresh-space", "invite_manager": False},
                              format="json").json()["invitation"] == "skipped"
    assert api(root).post(f"{BASE}/{row.pk}/approve", {}, format="json").status_code == 409


def test_request_changes_and_reject_go_through_the_workflow(django_capture_on_commit_callbacks):
    root = superadmin()
    changes, _ = public_row()
    rejected, _ = public_row(applicant_email="other@example.test")
    with django_capture_on_commit_callbacks(execute=True):
        assert api(root).post(f"{BASE}/{changes.pk}/request-changes", {"note": "Please add your hours."},
                              format="json").json()["status"] == "changes_requested"
        assert api(root).post(f"{BASE}/{rejected.pk}/reject", {"reason": "Outside our regions."},
                              format="json").json()["status"] == "rejected"
    detail = api(root).get(f"{BASE}/{changes.pk}").json()
    assert detail["revisions"][0]["kind"] == "changes_requested"


def test_staff_cannot_review_and_self_host_answers_404(settings):
    from tests.hosting_requests.helpers import member
    row, _ = public_row()
    assert api(member("plain")).get(BASE).status_code == 403
    settings.PLATFORM_DOMAIN_SUFFIX = ""
    assert api(superadmin()).get(BASE).status_code == 404
    assert api(superadmin("root-2")).post(f"{BASE}/{row.pk}/approve", {}, format="json").status_code == 404
