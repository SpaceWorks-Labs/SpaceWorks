"""#190: the web superadmin console's new paths do what /control/ did, through the same services."""

from unittest import mock

import pytest
from django.core.cache import cache

from apps.accounts.models import IPAccessRule, IPAutoBlock, User
from apps.audit.models import AuditLog
from tests.r2_superadmin_local.helpers import api, manager, space, superadmin

pytestmark = pytest.mark.django_db
A = "/api/v1/admin/platform/"


@pytest.fixture
def root():
    cache.clear()
    return superadmin("parity-api-root")


def test_staff_never_reach_the_parity_paths(root):
    boss = manager(space("parity-staff"))
    for path in ("ip-rules", "ip-blocks", "accounts?username=x", "oidc-providers", "restore-drills",
                 "restore-drills/settings", "archive-requests", "api-key-requests", "subdomain-requests"):
        assert api(boss).get(A + path).status_code in {401, 403}, path


def test_ip_rules_add_change_delete_with_the_control_audit_rows(root):
    client = api(root)
    created = client.post(A + "ip-rules", {"cidr": "198.51.100.7/24", "action": "allow", "note": "Office"}, format="json")
    assert created.status_code == 201 and created.json()["cidr"] == "198.51.100.0/24"
    rule_id = created.json()["id"]
    assert client.patch(A + f"ip-rules/{rule_id}", {"note": "HQ"}, format="json").json()["note"] == "HQ"
    assert client.delete(A + f"ip-rules/{rule_id}").status_code == 204
    saved = AuditLog.objects.filter(action="platform.ip_rule_saved").order_by("pk")
    assert [row.meta["via"] for row in saved] == ["console", "console"] and saved[1].meta["changed_fields"] == ["note"]
    assert AuditLog.objects.filter(action="platform.ip_rule_deleted", meta__via="console").exists()


def test_a_deny_rule_that_would_lock_the_superadmin_out_is_refused(root):
    response = api(root).post(A + "ip-rules", {"cidr": "127.0.0.0/8", "action": "deny"}, format="json",
                              REMOTE_ADDR="127.0.0.1")
    assert response.status_code == 400 and "lock you out" in str(response.json()["cidr"])
    assert not IPAccessRule.objects.exists()


def test_lifting_an_automatic_block_deletes_it_and_audits(root):
    from django.utils import timezone
    block = IPAutoBlock.objects.create(network="203.0.113.0/24", ip_key="k" * 64,
                                       blocked_until=timezone.now() + timezone.timedelta(hours=1))
    assert api(root).post(A + f"ip-blocks/{block.pk}/unblock").json() == {"unblocked": 1}
    assert not IPAutoBlock.objects.exists() and AuditLog.objects.filter(action="auth.ip_unblocked").exists()


def test_account_lookup_shows_no_contact_details_and_disable_runs_the_lifecycle(root):
    person = User.objects.create_user("parity-person", email="hidden@example.test", display_name="Hidden Name")
    found = api(root).get(A + "accounts", {"username": "parity-person"}).json()
    assert [row["id"] for row in found] == [person.pk]
    assert "hidden@example.test" not in str(found) and "Hidden Name" not in str(found)
    with mock.patch("apps.accounts.staff_account_lifecycle.disable_account") as disable:
        assert api(root).post(A + f"accounts/{person.pk}/disable", {"reason": "Abuse report"}, format="json").status_code == 200
    disable.assert_called_once_with(root, person.pk, reason="Abuse report")
    assert api(root).post(A + f"accounts/{person.pk}/disable", {"reason": "x"}, format="json").status_code == 400


def test_oidc_providers_are_added_and_disabled_never_deleted(root):
    client = api(root)
    body = {"slug": "campus", "display_name": "Campus", "issuer": "https://id.example.test",
            "jwks_url": "https://id.example.test/jwks", "client_id": "spaceworks", "is_enabled": True,
            "allow_auto_link": False}
    created = client.post(A + "oidc-providers", body, format="json")
    assert created.status_code == 201
    pk = created.json()["id"]
    assert client.patch(A + f"oidc-providers/{pk}", {"is_enabled": False}, format="json").json()["is_enabled"] is False
    assert client.delete(A + f"oidc-providers/{pk}").status_code == 405
    assert AuditLog.objects.filter(action="platform.oidc_provider_saved", meta__via="console").count() == 2


def test_drill_settings_change_and_a_drill_needs_a_restorable_backup(root, settings):
    client = api(root)
    changed = client.patch(A + "restore-drills/settings", {"restore_drill_interval_days": 14}, format="json")
    assert changed.status_code == 200 and changed.json()["restore_drill_interval_days"] == 14
    assert client.patch(A + "restore-drills/settings", {"restore_drill_interval_days": 400}, format="json").status_code == 400
    settings.TENANT_MIGRATION_AGE_IDENTITY_FILE, settings.TENANT_MIGRATION_AGE_RECIPIENT = "/tmp/id", "age1example"
    lab = space("parity-drill")
    assert client.post(A + "restore-drills", {"makerspace_id": lab.pk}, format="json").status_code == 409
    archive = mock.Mock(pk="00000000-0000-0000-0000-0000000000aa")
    with mock.patch("apps.backup.views_drills.latest_restorable_archive", return_value=archive), \
            mock.patch("apps.backup.tasks.run_restore_drill_now_task.delay") as delay, \
            mock.patch("apps.backup.views_drills.audit.record") as record:
        queued = client.post(A + "restore-drills", {"makerspace_id": lab.pk}, format="json")
    assert queued.status_code == 202 and queued.json()["status"] == "queued"
    delay.assert_called_once_with(archive.pk, root.pk)
    assert record.call_args.args[1] == "backup.drill_requested"


def test_a_self_host_move_is_decided_and_its_file_downloads_once(root, tmp_path):
    from apps.tenant_migration.models_selfhost_move import SelfHostMoveRequest

    lab = space("parity-move")
    move = SelfHostMoveRequest.objects.create(makerspace=lab, note="Moving out")
    client = api(root)
    assert [row["id"] for row in client.get(A + "selfhost-moves", {"status": "requested"}).json()["results"]] == [str(move.pk)]
    assert client.post(A + f"selfhost-moves/{move.pk}/approve", {"note": "OK"}, format="json").json()["status"] == "approved"
    artifact = tmp_path / "move.tar.age"
    artifact.write_bytes(b"age-encrypted")
    SelfHostMoveRequest.objects.filter(pk=move.pk).update(status="exported", artifact_path=str(artifact), artifact_sha256="d" * 64)
    url = client.post(A + f"selfhost-moves/{move.pk}/download-url").json()["url"]
    path = url.split("://", 1)[-1].split("/", 1)[1]
    from rest_framework.test import APIClient
    first = APIClient(HTTP_HOST="localhost").get("/" + path)
    assert first.status_code == 200 and b"".join(first.streaming_content) == b"age-encrypted"
    assert APIClient(HTTP_HOST="localhost").get("/" + path).status_code == 404
    assert AuditLog.objects.filter(action="selfhost_move.downloaded").count() == 1


def test_api_key_requests_are_issued_once_with_the_secret_and_audited(root):
    from apps.apiclients.models import ApiKeyRequest

    lab = space("parity-keys")
    # Fixture fix: every HMAC client needs >=1 exact origin (ApiClient.clean, "review fix #4"); the
    # request endpoint requires one (ApiKeyRequestSerializer) and an originless approval is refused
    # by design (tests/test_apiclient_validation.py), so this row must carry one like a real request.
    row = ApiKeyRequest.objects.create(makerspace=lab, requester=manager(lab), label="ERP sync",
                                       allowed_origins=["https://erp.example.test"])
    issued = api(root).post(A + f"api-key-requests/{row.pk}/approve")
    assert issued.status_code == 200 and issued.json()["client_secret"] and issued.json()["request"]["status"] == "approved"
    assert api(root).post(A + f"api-key-requests/{row.pk}/reject").status_code == 400
    assert AuditLog.objects.filter(action__in=("api_key_request.approved", "api_client.created")).count() == 2


def test_an_archive_request_decline_needs_a_note(root):
    from apps.makerspaces.models import MakerspaceArchiveRequest

    lab = space("parity-archive")
    row = MakerspaceArchiveRequest.objects.create(makerspace=lab, requested_by=manager(lab), reason="Closing")
    assert api(root).post(A + f"archive-requests/{row.pk}/decline", {}, format="json").status_code == 400
    declined = api(root).post(A + f"archive-requests/{row.pk}/decline", {"note": "Not yet"}, format="json")
    assert declined.status_code == 200 and declined.json()["status"] == "declined"


def test_chat_templates_validate_against_the_event_catalogue(root):
    lab = space("parity-chat")
    path = A + f"spaces/{lab.pk}/chat-templates"
    refused = api(root).post(path, {"feature": "nope", "event": "nope", "text_body": "x"}, format="json")
    assert refused.status_code == 400
    assert api(root).get(path).json()["count"] == 0
