"""Real control actions and key decisions: one-time secrets, replay and CORS reconciliation."""
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from django.contrib import admin, messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.exceptions import ValidationError
from django.test import RequestFactory
from django.utils import timezone

from apps.accounts import rbac
from apps.apiclients import key_request_decisions as decisions, notifications_p2
from apps.apiclients.admin_clients import ApiClientAdmin
from apps.apiclients.admin_requests import ApiKeyRequestAdmin
from apps.apiclients.models import ApiClient, ApiKeyRequest
from apps.apiclients.services import sync_makerspace_origins
from apps.audit.models import AuditLog
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from tests.accounts.account_factories import make_staff
from tests.accounts.ua1_helpers import platform

pytestmark = pytest.mark.django_db


@pytest.fixture
def setup(settings):
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode()
    space = Makerspace.objects.create(name="Key decisions", slug="cx6-key-decisions")
    manager = make_staff(space, username="cx6-key-manager")
    root = platform("cx6-key-root")
    return space, manager, root


def key_request(setup, label="Integration", **fields):
    space, manager, _ = setup
    return ApiKeyRequest.objects.create(makerspace=space, requester=manager, label=label,
                                        allowed_origins=["https://integration.test"], **fields)


def control_request(root):
    request = RequestFactory().post("/control/apiclients/")
    request.user, request.session = root, {}
    request._messages = FallbackStorage(request)
    return request


def test_approve_issues_one_secret_audits_both_changes_and_replay_cannot_duplicate(setup, monkeypatch):
    space, _, root = setup
    row = key_request(setup)
    at = datetime(2026, 11, 14, 10, 30, tzinfo=UTC)
    monkeypatch.setattr(timezone, "now", lambda: at)
    resolved, client, secret = decisions.approve(root, row)
    assert (resolved.status, resolved.resolved_by_id) == ("approved", root.pk)
    assert resolved.resolved_at == at
    assert (client.makerspace_id, client.created_by_id, client.client_type, client.scopes) == (
        space.pk, root.pk, "server", ["legacy:v1"])
    assert client.get_secret() == secret
    space.refresh_from_db()
    assert space.cors_allowed_origins == ["https://integration.test"]
    assert AuditLog.objects.get(action="api_key_request.approved", target_id=str(row.pk)).meta == {"api_client_id": client.pk}
    assert AuditLog.objects.get(action="api_client.created", target_id=str(client.pk)).meta == {
        "allowed_origins": ["https://integration.test"], "api_key_request_id": row.pk}
    monkeypatch.setattr(timezone, "now", lambda: at + timedelta(minutes=1))
    for decide in [decisions.approve, decisions.reject]:
        with pytest.raises(ValidationError) as error:
            decide(root, row)
        assert error.value.messages == ["This API key request is already decided."]
        resolved.refresh_from_db()
        assert resolved.resolved_at == at
    assert ApiClient.objects.filter(makerspace=space).count() == 1
    assert AuditLog.objects.filter(action="api_key_request.approved", target_id=str(row.pk)).count() == 1


def test_reject_does_not_issue_credentials_and_replay_is_refused(setup, monkeypatch):
    space, _, root = setup
    row = key_request(setup)
    at = datetime(2026, 11, 14, 10, 30, tzinfo=UTC)
    monkeypatch.setattr(timezone, "now", lambda: at)
    rejected = decisions.reject(root, row)
    assert (rejected.status, rejected.resolved_by_id) == ("rejected", root.pk)
    assert rejected.resolved_at == at
    assert ApiClient.objects.filter(makerspace=space).count() == 0
    assert AuditLog.objects.get(action="api_key_request.rejected", target_id=str(row.pk)).actor_id == root.pk
    monkeypatch.setattr(timezone, "now", lambda: at + timedelta(minutes=1))
    with pytest.raises(ValidationError) as error:
        decisions.reject(root, row)
    assert error.value.messages == ["This API key request is already decided."]
    rejected.refresh_from_db()
    assert rejected.resolved_at == at
    assert AuditLog.objects.filter(action="api_key_request.rejected", target_id=str(row.pk)).count() == 1


def test_control_batch_approval_skips_decided_rows_and_preserves_invalid_pending_requests(setup):
    _, _, root = setup
    valid = key_request(setup, "Valid")
    invalid = key_request(setup, "Invalid")
    invalid.allowed_origins = ["https://*.invalid.test"]
    invalid.save(update_fields=["allowed_origins"])
    decided = key_request(setup, "Decided", status="rejected")
    request = control_request(root)
    ApiKeyRequestAdmin(ApiKeyRequest, admin.site).approve_and_issue(request,
        ApiKeyRequest.objects.filter(pk__in=[valid.pk, invalid.pk, decided.pk]).order_by("pk"))
    valid.refresh_from_db()
    invalid.refresh_from_db()
    decided.refresh_from_db()
    assert [row.status for row in [valid, invalid, decided]] == ["approved", "pending", "rejected"]
    output = [(message.level, str(message)) for message in messages.get_messages(request)]
    assert [level for level, _ in output] == [messages.WARNING, messages.ERROR, messages.SUCCESS, messages.WARNING]
    assert output[-2:] == [(messages.SUCCESS, "Approved 1 API key request(s)."),
                            (messages.WARNING, "Skipped 1 non-pending API key request(s).")]
    assert ApiClient.objects.count() == 1
    assert AuditLog.objects.filter(action="api_key_request.approved").count() == 1


def test_control_batch_rejection_counts_only_new_decisions(setup):
    _, _, root = setup
    pending = key_request(setup, "Pending")
    decided = key_request(setup, "Old", status="approved")
    request = control_request(root)
    ApiKeyRequestAdmin(ApiKeyRequest, admin.site).reject_selected(request, ApiKeyRequest.objects.all())
    pending.refresh_from_db()
    decided.refresh_from_db()
    assert (pending.status, decided.status) == ("rejected", "approved")
    assert [(message.level, str(message)) for message in messages.get_messages(request)] == [
        (messages.SUCCESS, "Rejected 1 API key request(s)."),
        (messages.WARNING, "Skipped 1 non-pending API key request(s).")]
    assert AuditLog.objects.filter(action="api_key_request.rejected").count() == 1


def test_control_client_save_and_delete_sync_origins_and_retain_blank_secrets(setup):
    space, _, root = setup
    request = control_request(root)
    model_admin = ApiClientAdmin(ApiClient, admin.site)
    obj = ApiClient(label="Console", makerspace=space, allowed_origins=["https://console.test"])
    form = SimpleNamespace(cleaned_data={"smtp_host": "smtp.test", "smtp_port": 2525,
        "smtp_username": "mailer", "smtp_password": "mail-secret", "smtp_use_tls": True,
        "smtp_from_email": "desk@example.test", "telegram_bot_token": "bot-secret"})
    model_admin.save_model(request, obj, form, change=False)
    secret = obj.get_secret()
    assert obj.created_by_id == root.pk
    space.refresh_from_db()
    assert (space.smtp_port, space.smtp_use_tls, space.smtp_use_ssl) == (2525, True, False)
    assert space.get_smtp_password() == "mail-secret"
    assert space.get_telegram_bot_token() == "bot-secret"
    assert space.cors_allowed_origins == ["https://console.test"]
    obj.allowed_origins = ["https://updated.test"]
    model_admin.save_model(request, obj, SimpleNamespace(cleaned_data={}), change=True)
    space.refresh_from_db()
    assert obj.get_secret() == secret
    assert (space.smtp_port, space.smtp_host, space.smtp_use_tls) == (587, "", False)
    assert space.get_smtp_password() == "mail-secret"
    assert space.get_telegram_bot_token() == "bot-secret"
    assert space.cors_allowed_origins == ["https://updated.test"]
    pk = obj.pk
    model_admin.delete_model(request, obj)
    space.refresh_from_db()
    assert space.cors_allowed_origins == []
    assert ApiClient.objects.filter(pk=pk).count() == 0
    assert list(AuditLog.objects.filter(target_id=str(pk), target_type="apiclients.apiclient")
                .order_by("pk").values_list("action", flat=True)) == [
                    "api_client.created", "api_client.updated", "api_client.deleted"]


def test_control_bulk_delete_reconciles_each_tenant_and_preserves_other_clients(setup):
    space, _, root = setup
    other = Makerspace.objects.create(name="Other keys", slug="cx6-other-keys")
    first, _ = ApiClient.issue(label="First", makerspace=space,
        scopes=["public:catalogue:read"], allowed_origins=["https://first.test"])
    retained, _ = ApiClient.issue(label="Retained", makerspace=space,
        scopes=["public:catalogue:read"], allowed_origins=["https://retained.test"])
    second, _ = ApiClient.issue(label="Second", makerspace=other,
        scopes=["public:catalogue:read"], allowed_origins=["https://second.test"])
    for tenant in [space, other]:
        sync_makerspace_origins(tenant)
    ApiClientAdmin(ApiClient, admin.site).delete_queryset(control_request(root),
                                                        ApiClient.objects.filter(pk__in=[first.pk, second.pk]))
    space.refresh_from_db()
    other.refresh_from_db()
    assert space.cors_allowed_origins == ["https://retained.test"]
    assert other.cors_allowed_origins == []
    assert list(ApiClient.objects.values_list("pk", flat=True)) == [retained.pk]
    assert AuditLog.objects.filter(action="api_client.deleted").count() == 2


def test_notification_revision_audience_tenant_and_resolver_authority_are_revalidated(setup):
    space, manager, root = setup
    row = decisions.reject(root, key_request(setup, resolution_note="Contact the desk"))
    envelope = SimpleNamespace(makerspace_id=space.pk, source_id=str(row.pk), event="api_key_request_resolved",
        revision=notifications_p2.source_revision(row), audience="requester", recipient_id=manager.pk)
    assert notifications_p2.eligible(envelope) is True
    content = notifications_p2.render(envelope)
    assert content["subject"] == "Key decisions API access request rejected"
    assert "Note: Contact the desk" in content["text"]
    assert "No API secret is included in this notification." in content["text"]
    envelope.recipient_id = root.pk
    assert notifications_p2.eligible(envelope) is False
    envelope.audience = "staff"
    assert notifications_p2.eligible(envelope) is True
    assert notifications_p2.render(envelope)["subject"] == "API access request resolved"
    envelope.revision = "stale"
    assert notifications_p2.eligible(envelope) is False
    envelope.revision = notifications_p2.source_revision(row)
    envelope.event = "wrong_event"
    assert notifications_p2.eligible(envelope) is False
    envelope.event = "api_key_request_resolved"
    envelope.makerspace_id = 987654321
    assert notifications_p2.eligible(envelope) is False
    envelope.makerspace_id = space.pk
    row.resolved_by = None
    row.save(update_fields=["resolved_by"])
    assert notifications_p2.eligible(envelope) is False
    row.resolved_by = manager
    row.status = "pending"
    row.save(update_fields=["resolved_by", "status"])
    envelope.revision = notifications_p2.source_revision(row)
    assert notifications_p2.eligible(envelope) is False


@pytest.mark.parametrize("status", ["approved", "rejected"])
def test_resolved_notification_requires_the_resolvers_current_local_authority(setup, status, monkeypatch):
    space, manager, _ = setup
    monkeypatch.setattr(timezone, "now", lambda: datetime(2026, 11, 14, 10, 30, tzinfo=UTC))
    row = key_request(setup, status=status, resolved_by=manager, resolved_at=timezone.now())
    envelope = SimpleNamespace(makerspace_id=space.pk, source_id=str(row.pk), event="api_key_request_resolved",
        revision=notifications_p2.source_revision(row), audience="requester", recipient_id=manager.pk)
    assert rbac.can(manager, rbac.Action.MANAGE_MAKERSPACE, space.pk) is True
    assert notifications_p2.eligible(envelope) is True
    staff = MakerspaceMembership.staff_tracks.get(user=manager, makerspace=space)
    staff.assigned_role = space.roles.get(slug="inventory_manager")
    staff.role = staff.assigned_role.legacy_role or "custom"
    staff.save(update_fields=["assigned_role", "role"])
    row.refresh_from_db()
    assert (row.status, row.resolved_by_id) == (status, manager.pk)
    assert envelope.revision == notifications_p2.source_revision(row)
    assert rbac.can(row.resolved_by, rbac.Action.MANAGE_MAKERSPACE, space.pk) is False
    assert notifications_p2.eligible(envelope) is False

    foreign = Makerspace.objects.create(name="Foreign resolver", slug="cx6-foreign-resolver")
    foreign_manager = make_staff(foreign, username="cx6-foreign-key-manager")
    row.resolved_by = foreign_manager
    row.save(update_fields=["resolved_by", "updated_at"])
    envelope.revision = notifications_p2.source_revision(row)
    row.refresh_from_db()
    assert (row.status, row.resolved_by_id) == (status, foreign_manager.pk)
    assert envelope.revision == notifications_p2.source_revision(row)
    assert rbac.can(foreign_manager, rbac.Action.MANAGE_MAKERSPACE, foreign.pk) is True
    assert rbac.can(foreign_manager, rbac.Action.MANAGE_MAKERSPACE, space.pk) is False
    assert notifications_p2.eligible(envelope) is False


def test_global_control_client_has_no_tenant_settings_or_public_identifiers(setup):
    _, _, root = setup
    model_admin = ApiClientAdmin(ApiClient, admin.site)
    obj = ApiClient(label="Global", makerspace=None, allowed_origins=["https://platform.test"])
    request = control_request(root)
    model_admin.save_model(request, obj, SimpleNamespace(cleaned_data={}), change=False)
    assert model_admin.makerspace_public_code(obj) == "-"
    assert model_admin.makerspace_public_api_key(obj) == "-"
    assert obj.created_by_id == root.pk
    assert obj.get_secret()
    row = AuditLog.objects.get(action="api_client.created", target_id=str(obj.pk), target_type="apiclients.apiclient")
    assert row.makerspace_id is None
    assert row.meta == {"surface": "control"}
    model_admin.delete_model(request, obj)
    assert ApiClient.objects.count() == 0
