"""X31 hosting requests: changes requested (control only), applicant resubmit, history, wipe."""
from datetime import timedelta

import pytest
from django.test import override_settings
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from apps.audit.models import AuditLog
from apps.hosting_requests import retention, tokens, workflow
from apps.hosting_requests.exceptions import HostingRequestConflict
from apps.hosting_requests.models import HostingRequest, HostingRequestRevision
from tests.organizations.test_org_authority import make_user

pytestmark = pytest.mark.django_db


def submitted():
    raw, digest = tokens.mint()
    row = HostingRequest.objects.create(
        status="submitted", source="public", applicant_name="Ada", applicant_email="ada@example.test",
        space_name="Old name", location="Kochi", description="A community workshop for everyone.",
        access_token_digest=digest, verified_at=timezone.now())
    return row


@pytest.fixture
def platform(monkeypatch):
    monkeypatch.setattr("apps.hosting_requests.applicant.admin_available", lambda: True)
    sent = []
    monkeypatch.setattr("apps.hosting_requests.notifications.schedule_changes_requested",
                        lambda row, raw: sent.append(raw))
    monkeypatch.setattr("apps.hosting_requests.notifications.schedule_new", lambda row: None)
    return make_user("hosting-root", is_superuser=True, account_kind="platform"), sent


def test_request_changes_then_resubmit_returns_to_review_with_history(platform):
    root, sent = platform
    row = submitted()
    workflow.request_changes(root, row.pk, "Please add your opening hours.")
    row.refresh_from_db()
    assert row.status == "changes_requested" and row.changes_note
    resubmitted = workflow.resubmit(sent[0], {"space_name": "New name", "location": "Kochi"}, "Added hours")
    assert resubmitted.status == "submitted" and resubmitted.space_name == "New name"
    assert resubmitted.changes_note == "" and resubmitted.changes_requested_at is None
    kinds = list(HostingRequestRevision.objects.filter(request=row).values_list("kind", "changed_fields"))
    assert kinds == [("changes_requested", []), ("resubmitted", ["space_name"])]
    assert AuditLog.objects.filter(action="hosting_request.resubmitted").exists()
    with pytest.raises(HostingRequestConflict):
        workflow.resubmit(sent[0], {"space_name": "Again"})


def test_only_the_superadmin_can_ask_for_changes(platform):
    row = submitted()
    with pytest.raises(PermissionDenied):
        workflow.request_changes(make_user("not-root"), row.pk, "Please add more detail here.")


def test_resubmit_switch_off_is_a_404(platform):
    from django.http import Http404
    root, sent = platform
    row = submitted()
    workflow.request_changes(root, row.pk, "Please add your opening hours.")
    with override_settings(HOSTING_REQUEST_RESUBMIT_ENABLED=False), pytest.raises(Http404):
        workflow.resubmit(sent[0], {"space_name": "New name"})


def test_unanswered_requests_are_wiped_after_ninety_days(platform):
    root, _sent = platform
    row = submitted()
    workflow.request_changes(root, row.pk, "Please add your opening hours.")
    HostingRequest.objects.filter(pk=row.pk).update(changes_requested_at=timezone.now() - timedelta(days=91))
    retention.sweep()
    row.refresh_from_db()
    assert row.redacted_at and row.applicant_email == "" and row.changes_note == ""
    assert HostingRequestRevision.objects.get(request=row).note == ""
