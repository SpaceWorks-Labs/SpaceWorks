"""The merged graph revokes legacy authority without rewriting principal kinds."""

import importlib
from datetime import datetime, timezone as dt_timezone, timedelta
from types import SimpleNamespace

import pytest
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from tests.account_split.test_p1_data_migration import historical_tables

pytestmark = pytest.mark.django_db(transaction=True)
BEFORE = [("accounts", "0040_merge_mobile_account_split"),
          ("integrations", "0040_merge_mobile_notifications")]
AFTER = [("accounts", "0041_reconcile_native_account_context")]


def test_forward_reconciliation_revokes_misclassified_grant_and_preserves_member(monkeypatch):
    now = datetime(2026, 11, 14, 12, 30, tzinfo=dt_timezone.utc)
    monkeypatch.setattr(timezone, "now", lambda: now)
    labels = ["accounts." + name for name in (
        "User", "NativeAppRegistration", "DeviceGrant", "DeviceRefreshFamily", "DeviceRefreshToken",
        "AccountPurgeProgress", "AccountPurgeObject", "AppleRevocation", "AccountRestoreIntent",
        "AppleRefreshCredential", "SocialIdentity", "PasswordResetEnvelope")]
    labels.append("integrations.PushDevice")
    with historical_tables(BEFORE, labels) as state:
        User = state.get_model("accounts", "User")
        App = state.get_model("accounts", "NativeAppRegistration")
        Grant = state.get_model("accounts", "DeviceGrant")
        Family = state.get_model("accounts", "DeviceRefreshFamily")
        user = User.objects.create(username="reconciliation-history", account_kind="member",
                                   role="requester", is_active=True, credential_generation=3)
        app = App.objects.create(app_id="org.spaceworks.history", platform="apple", environment="production",
                                 status="approved", verifier_config_key="history", signing_identities=["TEAMID1234"])
        values = dict(user=user, registration=app, app_id=app.app_id, platform=app.platform,
                      environment=app.environment, signing_identity="TEAMID1234",
                      attested_at=now, last_used_at=now)
        invalid = Grant.objects.create(authority="staff", **values)
        valid = Grant.objects.create(authority="member", **values)
        family = Family.objects.create(user=user, grant=invalid)
        module = importlib.import_module("apps.accounts.migrations.0041_reconcile_native_account_context")
        # Apply just this migration: its fields, reconciliation and immutable-authority guards.
        from django.db.migrations.state import ProjectState
        step = module.Migration(AFTER[0][1], "accounts")
        with connection.schema_editor() as editor:
            final = step.apply(ProjectState.from_apps(state), editor).apps
        Grant = final.get_model("accounts", "DeviceGrant")
        invalid, valid = Grant.objects.get(pk=invalid.pk), Grant.objects.get(pk=valid.pk)
        assert (invalid.status, invalid.revoked_at) == ("revoked", now)
        assert valid.status == "active" and valid.authority == "member"
        assert valid.credential_generation == 3 and valid.staff_makerspace_id is None
        assert final.get_model("accounts", "User").objects.get(pk=user.pk).account_kind == "member"
        Family = final.get_model("accounts", "DeviceRefreshFamily")
        assert Family.objects.get(pk=family.pk).revoked_at == now
        assert valid.revoked_at is None
        # Restarting the data conversion cannot reactivate anything or relabel authority.
        module = importlib.import_module("apps.accounts.migrations.0041_reconcile_native_account_context")
        replay_time = now + timedelta(hours=1)
        monkeypatch.setattr(timezone, "now", lambda: replay_time)
        module.reconcile_existing_authority(final, SimpleNamespace(connection=connection))
        invalid.refresh_from_db()
        valid.refresh_from_db()
        assert (invalid.status, invalid.revoked_at) == ("revoked", now)
        assert Family.objects.get(pk=family.pk).revoked_at == now
        assert (valid.status, valid.revoked_at, valid.credential_generation) == ("active", None, 3)
        with pytest.raises(IntegrityError), transaction.atomic():
            Grant.objects.filter(pk=invalid.pk).update(status="active", revoked_at=None)
