from contextlib import contextmanager
from unittest.mock import Mock
import os
import uuid

import pytest

from apps.backup.managed import admission
from apps.backup.managed.admission import ManagedAdmissionError
from apps.backup.managed.mode_binding import assert_mode_binding
from apps.backup.managed.release import _existing


def cursor_with(*rows):
    cursor = Mock()
    cursor.fetchone.side_effect = rows
    return cursor


@pytest.mark.parametrize("row", [None, ("target_import", None), ("quarantined", None), ("quiesced", None), ("unknown", None), ("normal", uuid.uuid4())])
def test_unknown_or_non_normal_recovery_state_refuses(row):
    cursor = cursor_with(row)
    with pytest.raises(ManagedAdmissionError):
        admission.assert_recovery_normal(cursor)


def test_normal_recovery_admits_without_a_reservation_query():
    # P1b: Lane E restore components and reservations no longer exist (backup/0032).
    cursor = cursor_with(("normal", None))
    admission.assert_recovery_normal(cursor)
    assert cursor.execute.call_count == 1


def test_host_env_cannot_admit_an_already_managed_bound_database():
    with pytest.raises(ManagedAdmissionError):
        assert_mode_binding(cursor_with(("backup_manageddeploymentstate",), (True,)), "host")


def test_host_database_without_new_table_is_unchanged():
    cursor = cursor_with((None,))
    assert_mode_binding(cursor, "host")
    assert cursor.execute.call_count == 1


def test_release_refuses_existing_database_without_adoption_before_migrate():
    cursor = cursor_with(("django_migrations",), ("normal", None), (None, None), (None,))
    with pytest.raises(ManagedAdmissionError, match="adoption"):
        _existing(cursor, adopt=False)


def test_release_cannot_adopt_a_restored_candidate():
    cursor = cursor_with(("django_migrations",), ("normal", None), (uuid.uuid4(), uuid.uuid4()))
    with pytest.raises(ManagedAdmissionError):
        _existing(cursor, adopt=True)


@pytest.mark.parametrize("name", ["DATABASE_MAINTENANCE_URL", "SPACEWORKS_MAINTENANCE_DATABASE_URL", "CLOUD_SCRATCH_DATABASES_FILE"])
def test_ordinary_services_refuse_job_secrets(name):
    with pytest.raises(ManagedAdmissionError, match="credentials"):
        admission.assert_managed_admission({name: "do-not-print"})


@pytest.fixture
def release_environment(monkeypatch):
    """Keep real Django setup/models; isolate provider connections and DDL/grants."""
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from django.core import management
    from apps.backup.managed import release
    from apps.backup.models_host_identity import DeploymentDatabaseIdentity
    from config.cloud_database import guards

    DeploymentDatabaseIdentity.load()
    identity = uuid.uuid4()
    specs = (SimpleNamespace(parameters={"dbname": "test", "user": "runtime"}),
             SimpleNamespace(parameters={"dbname": "test", "user": "maintenance"}, mode="direct"))
    database = MagicMock()
    database.__enter__.return_value = database
    cursor = database.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (True,)
    monkeypatch.setattr(release, "release_specs", lambda: specs)
    monkeypatch.setattr(release, "deployment_id", lambda: identity)
    monkeypatch.setattr(release, "database_principal", lambda spec: spec.parameters["user"])
    monkeypatch.setattr(release, "connect_database", lambda *args: database)
    monkeypatch.setattr(release, "_existing", lambda *args, **kwargs: False)
    for name in ("probe_session_transport", "prepare_private_defaults", "application_tables",
                 "probe_extensions", "provision_runtime_role", "apply_managed_grants",
                 "grant_required_extensions", "assert_binding", "prove_runtime_rights"):
        monkeypatch.setattr(release, name, Mock())
    guard = Mock(unsafe=True)  # the guard API is assert_valid()
    monkeypatch.setattr(guards, "TransactionGuard", lambda *args: guard)
    monkeypatch.setenv("DATABASE_MAINTENANCE_URL", "postgres://maintenance:private@db/test")
    # run_release() repoints DATABASE_URL/DATABASE_CONNECTION_MODE for its own finite
    # process; register both so teardown restores this pytest process's values.
    monkeypatch.setenv("DATABASE_URL", os.environ.get("DATABASE_URL", ""))
    monkeypatch.setenv("DATABASE_CONNECTION_MODE", os.environ.get("DATABASE_CONNECTION_MODE", "direct"))
    for key, value in {
        "USERNAME": "cloud-bootstrap-owner", "EMAIL": "owner@example.test",
        "PASSWORD": "generated-private-credential", "PASSWORD_GENERATED": "True",
    }.items():
        monkeypatch.setenv("SETUP_SUPERADMIN_" + key, value)
    for key, value in {"MAKERSPACE_NAME": "Confirmed Lab", "MAKERSPACE_SLUG": "confirmed-lab",
                       "ORGANIZATION_NAME": "Confirmed Organization", "MODULE_PROFILE": "minimal"}.items():
        monkeypatch.setenv("SETUP_" + key, value)
    real_command = management.call_command
    commands = []

    def command(name, **kwargs):
        guard.assert_valid()
        commands.append(name)
        if name != "migrate":
            return real_command(name, **kwargs)

    monkeypatch.setattr(management, "call_command", command)
    return release, commands, guard


@pytest.mark.django_db
def test_release_executes_confirmed_setup_and_rerun_preserves_account(release_environment):
    from django.contrib.auth import get_user_model
    from apps.makerspaces.models import Makerspace
    from apps.organizations.models import OrganizationMakerspace

    release, commands, guard = release_environment
    release.run_release()
    assert commands == ["migrate", "setup_instance"]
    account = get_user_model().objects.get(username="cloud-bootstrap-owner")
    assert account.account_kind == "platform" and account.is_superuser
    assert account.check_password("generated-private-credential") and account.must_change_password
    space = Makerspace.objects.get(slug="confirmed-lab")
    owner = OrganizationMakerspace.objects.get(makerspace=space, relationship="owner")
    assert owner.organization.name == "Confirmed Organization"
    assert space.name == "Confirmed Lab"
    account.set_password("operator-changed-password")
    account.save(update_fields=["password"])
    release.run_release()
    account.refresh_from_db()
    assert commands == ["migrate", "setup_instance", "migrate", "setup_instance"]
    assert account.check_password("operator-changed-password")
    assert Makerspace.objects.filter(slug="confirmed-lab").count() == 1
    assert OrganizationMakerspace.objects.filter(makerspace=space).count() == 1
    guard.assert_valid.assert_called()


@pytest.mark.django_db
def test_regular_release_without_setup_answers_does_not_bootstrap_defaults(release_environment, monkeypatch):
    release, commands, _ = release_environment
    monkeypatch.delenv("SETUP_SUPERADMIN_USERNAME")
    release.run_release()
    assert commands == ["migrate"]


@pytest.mark.django_db
def test_setup_failure_aborts_release_before_grants(release_environment, monkeypatch):
    from django.core import management

    release, commands, _ = release_environment
    original = management.call_command

    def fail(name, **kwargs):
        if name == "setup_instance":
            raise RuntimeError("setup failed")
        return original(name, **kwargs)

    monkeypatch.setattr(management, "call_command", fail)
    with pytest.raises(RuntimeError, match="setup failed"):
        release.run_release()
    assert commands == ["migrate"]
    release.provision_runtime_role.assert_not_called()
