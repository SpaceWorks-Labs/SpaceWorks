"""Integration migrations and custody constraints; run in the isolated PG runner."""
from datetime import date
import json
from pathlib import Path
from uuid import uuid4

import pytest
from django.apps import apps
from django.db import DatabaseError, transaction
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.autodetector import MigrationAutodetector
from django.db.migrations.state import ProjectState


def test_cloud_migration_state_matches_registered_models(monkeypatch):
    from apps.makerspaces.models import Makerspace, default_enabled_modules
    # tests/conftest.py's autouse fixture swaps this field default for test data only;
    # compare the real model state the migrations must match.
    monkeypatch.setattr(Makerspace._meta.get_field("enabled_modules"), "default", default_enabled_modules)
    # The autouse fixture swaps the enabled_features default as well (tests/conftest.py).
    from apps.makerspaces.capabilities import default_enabled_features
    monkeypatch.setattr(Makerspace._meta.get_field("enabled_features"), "default", default_enabled_features)
    loader = MigrationLoader(None)
    changes = MigrationAutodetector(loader.project_state(), ProjectState.from_apps(apps)).changes(graph=loader.graph)
    assert not changes


def test_every_cloud_model_has_explicit_omission_and_field_snapshot():
    from apps.data_export.models import OMITTED_MODELS
    from apps.tenant_migration.tenant_dump_field_snapshot import FIRST_PARTY_FIELD_NAMES
    root = Path(__file__).resolve().parents[4]
    manifest = json.loads((root / "deploy/contracts/cloud-model-fields.json").read_text())
    for label, names in manifest.items():
        model = apps.get_model(label)
        assert label in OMITTED_MODELS
        assert set(names) == {field.name for field in model._meta.concrete_fields}
        assert set(names) == FIRST_PARTY_FIELD_NAMES[label]


@pytest.mark.django_db
def test_managed_binding_is_absent_until_release_and_immutable_once_created():
    from apps.backup.models import ManagedDeploymentState
    assert not ManagedDeploymentState.objects.exists()
    row = ManagedDeploymentState.objects.create(pk=1, deployment_id=uuid4(), database_uuid=uuid4())
    with pytest.raises(DatabaseError), transaction.atomic():
        ManagedDeploymentState.objects.filter(pk=row.pk).update(deployment_id=uuid4())
    with pytest.raises(DatabaseError), transaction.atomic():
        ManagedDeploymentState.objects.filter(pk=row.pk).delete()


@pytest.mark.django_db
def test_storage_history_floor_cannot_be_downgraded_or_deleted():
    from apps.operations.models import StorageCapabilityState
    row = StorageCapabilityState.objects.create(identity_fingerprint="a"*64,
        identity={"endpoint":"https://store.example.org","region":"auto","bucket":"private"},
        logical_role="private", configuration_fingerprint="b"*64, history_possible=True)
    with pytest.raises(DatabaseError), transaction.atomic():
        StorageCapabilityState.objects.filter(pk=row.pk).update(history_possible=False)
    with pytest.raises(DatabaseError), transaction.atomic():
        StorageCapabilityState.objects.filter(pk=row.pk).delete()


@pytest.mark.django_db
def test_mail_charge_survives_log_deletion():
    from apps.integrations.models import EmailLog
    from apps.operations.models import CloudEmailBudgetAccount, CloudEmailReservation
    account = CloudEmailBudgetAccount.objects.create(key="billing-account", provider="resend", reset_timezone="UTC")
    log = EmailLog.objects.create(to_email="", subject="redacted")
    receipt = CloudEmailReservation.objects.create(account=account, log=log, attempt_key="attempt-1",
        provider="resend", day=date.today(), month=date.today().replace(day=1), recipients=1, state="uncertain")
    log.delete()
    receipt.refresh_from_db()
    assert receipt.log_id is None
    assert receipt.state == "uncertain"
    assert receipt.recipients == 1
