"""The merged graph revokes legacy authority without rewriting principal kinds."""

import importlib

import pytest
from django.db import connection, transaction, IntegrityError
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

pytestmark = pytest.mark.django_db(transaction=True)
BEFORE = [("accounts", "0040_merge_mobile_account_split"),
          ("integrations", "0040_merge_mobile_notifications")]
AFTER = [("accounts", "0041_reconcile_native_account_context")]


def test_forward_reconciliation_revokes_misclassified_grant_and_preserves_member():
    executor = MigrationExecutor(connection)
    leaves = executor.loader.graph.leaf_nodes()
    try:
        executor.migrate(BEFORE)
        state = executor.loader.project_state(BEFORE).apps
        User = state.get_model("accounts", "User")
        App = state.get_model("accounts", "NativeAppRegistration")
        Grant = state.get_model("accounts", "DeviceGrant")
        Family = state.get_model("accounts", "DeviceRefreshFamily")
        now = timezone.now()
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
        executor = MigrationExecutor(connection)
        executor.migrate(AFTER)
        final = executor.loader.project_state(AFTER).apps
        Grant = final.get_model("accounts", "DeviceGrant")
        invalid, valid = Grant.objects.get(pk=invalid.pk), Grant.objects.get(pk=valid.pk)
        assert invalid.status == "revoked" and invalid.revoked_at
        assert valid.status == "active" and valid.authority == "member"
        assert valid.credential_generation == 3 and valid.staff_makerspace_id is None
        assert final.get_model("accounts", "User").objects.get(pk=user.pk).account_kind == "member"
        assert final.get_model("accounts", "DeviceRefreshFamily").objects.get(pk=family.pk).revoked_at
        # Restarting the data conversion cannot reactivate anything or relabel authority.
        module = importlib.import_module("apps.accounts.migrations.0041_reconcile_native_account_context")
        with connection.schema_editor() as editor:
            module.reconcile_existing_authority(final, editor)
        assert Grant.objects.get(pk=invalid.pk).status == "revoked"
        with pytest.raises(IntegrityError), transaction.atomic():
            Grant.objects.filter(pk=invalid.pk).update(status="active", revoked_at=None)
    finally:
        # Restore every app, including consumers whose latest migration was unapplied.
        MigrationExecutor(connection).migrate(leaves)
