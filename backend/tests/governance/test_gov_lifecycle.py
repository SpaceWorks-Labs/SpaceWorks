"""Hidden lifecycle decisions remain narrow, audited platform governance."""

from types import SimpleNamespace

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.makerspaces import archive_requests, lifecycle
from apps.makerspaces.models import Makerspace, MakerspaceArchiveRequest
from tests.accounts.account_factories import make_staff

pytestmark = pytest.mark.django_db


def platform():
    return User.objects.create_superuser(username="gov-operator", email="operator@example.test",
                                        password="safe-operator-password", account_kind="platform")


def hidden(**values):
    return Makerspace.objects.create(name="Sovereign workshop", slug="gov-hidden", **values)


def test_hidden_archive_unarchive_audit_and_impact():
    actor, space = platform(), hidden()
    assert set(lifecycle.archive_impact(space)) == {"owned_pending", "routed_pending", "total_pending", "unpaid_event_payouts"}
    lifecycle.archive(space, actor)
    space.refresh_from_db()
    assert space.archived_at and space.archived_by == actor
    lifecycle.unarchive(space, actor)
    space.refresh_from_db()
    assert space.archived_at is None
    for action in ("makerspace.archived", "makerspace.unarchived"):
        assert "superadmin_access_enabled" not in AuditLog.objects.get(action=action, makerspace=space).meta


@pytest.mark.parametrize("operation", ["archive", "unarchive", "purge", "approve", "decline"])
@pytest.mark.parametrize("kind", ["member", "staff"])
def test_services_reject_nonplatform_even_if_superuser_flag_is_supplied(operation, kind):
    space = hidden()
    requester = User.objects.create_user(username="requester", email="requester@example.test")
    pending = MakerspaceArchiveRequest.objects.create(makerspace=space, requested_by=requester, reason="Close")
    actor = SimpleNamespace(is_authenticated=True, account_kind=kind, is_superuser=True,
                            is_active=True, retired_at=None, access_status="active", must_change_password=False)
    with pytest.raises(ValidationError, match="platform superadmin"):
        if operation in {"approve", "decline"}:
            getattr(archive_requests, operation)(pending, actor, "Governance decision")
        else:
            getattr(lifecycle, operation)(space, actor)
    space.refresh_from_db()
    pending.refresh_from_db()
    assert space.archived_at is None and pending.status == "pending"


def test_hidden_space_manager_request_can_be_approved_then_purged(monkeypatch):
    monkeypatch.setattr(archive_requests, "schedule_created", lambda pk: None)
    monkeypatch.setattr(archive_requests, "schedule_resolved", lambda pk: None)
    monkeypatch.setattr(lifecycle, "_delete_storage_keys", lambda keys: None)
    monkeypatch.setattr(lifecycle, "_delete_public_image_keys", lambda keys: None)
    space, actor = hidden(), platform()
    manager = make_staff(space, username="gov-manager", role=User.Role.SPACE_MANAGER)
    pending = archive_requests.create(space, manager, "Workshop closed permanently")
    archive_requests.approve(pending, actor)
    pending.refresh_from_db()
    assert pending.status == "approved"
    space.refresh_from_db()
    stale = Makerspace.objects.get(pk=space.pk)
    space_id = space.pk
    lifecycle.purge(stale, actor)
    assert not Makerspace.objects.filter(pk=space_id).exists()
    completed = AuditLog.objects.get(action="makerspace.purged", makerspace=None)
    assert completed.meta["makerspace_id"] == space_id
    assert "superadmin_access_enabled" not in completed.meta
    manager.refresh_from_db()
    # One account per person (U-C): a purge retires nobody; only the space's staff row goes.
    from apps.makerspaces.models import MakerspaceMembership
    assert manager.retired_at is None and manager.is_active and manager.account_kind == "member"
    assert not MakerspaceMembership.all_tracks.filter(user=manager, makerspace_id=space_id).exists()


