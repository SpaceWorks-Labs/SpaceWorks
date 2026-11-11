import pytest
from django.http import Http404
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit.models import AuditLog
from apps.hosting_requests import workflow
from apps.hosting_requests.exceptions import HostingRequestConflict
from apps.hosting_requests.models import HostingRequest
from tests.hosting_requests.helpers import (
    invited_row, payload, public_row, space, space_manager, superadmin,
)

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("managed")]
S = HostingRequest.Status


def audit_actions(row):
    return list(
        AuditLog.objects.filter(target_type="hosting_requests.hostingrequest", target_id=str(row.pk))
        .order_by("id").values_list("action", flat=True)
    )


def test_public_create_is_unaudited_and_verify_writes_one_audit_row(django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        row, raw = workflow.create_public(payload())
    assert row.status == S.PENDING_VERIFICATION and row.applicant_email == "ada@example.test"
    assert audit_actions(row) == []
    with django_capture_on_commit_callbacks(execute=True):
        opened = workflow.open_by_token(raw)
    assert opened.status == S.SUBMITTED and opened.verified_at is not None
    assert audit_actions(row) == ["hosting_request.submitted"]
    entry = AuditLog.objects.get(action="hosting_request.submitted")
    assert entry.meta.get("source") == "public"
    # A second open is a read: no new transition, no new audit row.
    assert workflow.open_by_token(raw).status == S.SUBMITTED
    assert audit_actions(row) == ["hosting_request.submitted"]


def test_accept_and_reject_each_write_exactly_one_literal_audit_row():
    root = superadmin()
    accepted, _ = public_row()
    workflow.accept(root, accepted.pk)
    assert audit_actions(accepted) == ["hosting_request.accepted"]
    rejected, _ = public_row()
    workflow.reject(root, rejected.pk, "Outside the regions we host.")
    rejected.refresh_from_db()
    assert rejected.status == S.REJECTED and rejected.rejection_reason == "Outside the regions we host."
    assert audit_actions(rejected) == ["hosting_request.rejected"]
    # The reason is free text and stays out of the append-only log.
    assert "regions" not in str(AuditLog.objects.get(action="hosting_request.rejected").meta)


@pytest.mark.parametrize("status", [S.PENDING_VERIFICATION, S.ACCEPTED, S.REJECTED, S.WITHDRAWN])
def test_accept_from_any_other_state_is_a_409(status):
    row, _ = public_row(status=status)
    with pytest.raises(HostingRequestConflict) as caught:
        workflow.accept(superadmin(), row.pk)
    assert caught.value.status_code == 409
    assert caught.value.detail["code"] == "invalid_transition"


@pytest.mark.parametrize("status", [S.PENDING_VERIFICATION, S.REJECTED, S.WITHDRAWN])
def test_reject_from_a_disallowed_state_is_a_409(status):
    row, _ = public_row(status=status)
    with pytest.raises(HostingRequestConflict):
        workflow.reject(superadmin(), row.pk, "A sufficiently long reason.")


@pytest.mark.parametrize("reason", ["", "   ", "too short", "x" * 2001])
def test_reject_needs_a_ten_to_two_thousand_character_reason(reason):
    row, _ = public_row()
    with pytest.raises(ValidationError):
        workflow.reject(superadmin(), row.pk, reason)
    row.refresh_from_db()
    assert row.status == S.SUBMITTED


def test_unlinked_accepted_request_can_still_be_rejected_but_not_after_linking():
    root = superadmin()
    row, _ = public_row(status=S.ACCEPTED)
    workflow.reject(root, row.pk, "Changed our mind after review.")
    linked, _ = public_row(status=S.ACCEPTED)
    target = space("linked-space")
    workflow.link_created_makerspace(root, linked.pk, target)
    with pytest.raises(HostingRequestConflict):
        workflow.reject(root, linked.pk, "Too late to reject this one.")


def test_link_refuses_non_accepted_and_already_linked_rows():
    root = superadmin()
    submitted, _ = public_row()
    with pytest.raises(HostingRequestConflict):
        workflow.link_created_makerspace(root, submitted.pk, space("link-a"))
    accepted, _ = public_row(status=S.ACCEPTED)
    workflow.link_created_makerspace(root, accepted.pk, space("link-b"))
    assert audit_actions(accepted) == ["hosting_request.makerspace_linked"]
    with pytest.raises(HostingRequestConflict):
        workflow.link_created_makerspace(root, accepted.pk, space("link-c"))


def test_decisions_need_a_superadmin():
    row, _ = public_row()
    manager = space_manager(space("not-root"))
    with pytest.raises(PermissionDenied):
        workflow.accept(manager, row.pk)


def test_decisions_are_refused_on_self_host(settings):
    settings.PLATFORM_DOMAIN_SUFFIX = ""
    row, _ = public_row()
    with pytest.raises(PermissionDenied):
        workflow.accept(superadmin(), row.pk)


def test_expired_verification_link_is_a_404_and_does_not_transition():
    from datetime import timedelta
    from django.utils import timezone

    row, raw = public_row(
        status=S.PENDING_VERIFICATION, verification_expires_at=timezone.now() - timedelta(minutes=1),
    )
    with pytest.raises(Http404):
        workflow.open_by_token(raw)
    row.refresh_from_db()
    assert row.status == S.PENDING_VERIFICATION


def test_cancel_from_submitted_is_a_409():
    makerspace = space("cancel-submitted")
    manager = space_manager(makerspace)
    row, _ = invited_row(makerspace=makerspace, status=S.SUBMITTED, invited_by=manager)
    with pytest.raises(HostingRequestConflict):
        workflow.cancel_invitation(manager, pk=row.pk, makerspace_id=makerspace.pk)


@pytest.mark.django_db(transaction=True)
def test_purging_the_inviter_makerspace_nulls_the_link_and_keeps_the_row(monkeypatch):
    from django.utils import timezone

    from apps.makerspaces import lifecycle

    makerspace = space("purged-inviter", archived_at=timezone.now())
    row, _ = invited_row(makerspace=makerspace)
    monkeypatch.setattr(lifecycle, "_delete_storage_keys", lambda _keys: None)
    monkeypatch.setattr(lifecycle, "_delete_public_image_keys", lambda _keys: None)
    lifecycle.purge(makerspace, superadmin("purge-root"))
    row.refresh_from_db()
    assert row.inviter_makerspace_id is None and row.status == S.INVITED
