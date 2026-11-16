"""PostgreSQL reruns: mandatory envelopes must survive optional-mode rollback.

Requires R's retained model dependency and the isolated project test runner.
"""
import json
from uuid import uuid4

from cryptography.fernet import Fernet
import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.utils import timezone

from apps.encryption.cache import dek_cache
from apps.encryption.crypto import PiiKeyUnavailable
from apps.encryption.maintenance import write_legacy_values
from apps.encryption.models import MakerspaceEncryptionKey
from apps.encryption.services import disable_dek
from apps.encryption.tenant_preparation import prepare_tenant_key, tenant_key_context
from apps.encryption.write_fence import PiiWriteFenced, close_makerspace
from apps.makerspaces.models import Makerspace
from apps.payments.models import EventPayeeRevision, EventPayoutObligation

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def finance_rows(settings):
    settings.PII_ENCRYPTION_ENABLED = False
    settings.PII_KEY_BROKER = "local"
    settings.PII_MASTER_KEY = Fernet.generate_key().decode()
    settings.PII_SEARCH_HASH_KEY = ""  # Mandatory fields do not require a search generation.
    dek_cache.clear()
    space = Makerspace.objects.create(name="Finance fixture", slug="g1-finance")
    member = get_user_model().objects.create_user(username="g1-owner", account_kind="member")
    obligation = EventPayoutObligation.objects.create(
        makerspace=space, owner_member=member, event_id_snapshot=41,
        event_title_snapshot="Event", source_uuid=uuid4(), source_decision_revision=1,
        currency="INR", approved_minor=125000, domain_coordination_state="detached",
    )
    yield space, member, obligation
    dek_cache.clear()


def payee(obligation, member):
    return EventPayeeRevision.objects.create(
        obligation=obligation, owner=member, country="IN", template_key="in_bank",
        template_version=1, method="bank_transfer", details=json.dumps({"account_number": "00123456"}),
        submitted_at=timezone.now(), disclosure_version=1,
    )


def raw_details(row):
    with connection.cursor() as cursor:
        cursor.execute("SELECT details FROM payments_eventpayeerevision WHERE id=%s", [row.pk])
        return cursor.fetchone()[0]


def test_mandatory_raw_orm_encrypts_with_optional_pii_off_and_partial_save_preserves_envelope(finance_rows, settings):
    _, owner, obligation = finance_rows
    row = payee(obligation, owner)
    raw = raw_details(row)
    assert raw.startswith("pii:gcm:v1:")
    assert "00123456" not in raw
    loaded = EventPayeeRevision.objects.get(pk=row.pk)
    assert json.loads(loaded.details)["account_number"] == "00123456"
    loaded.version += 1
    loaded.save(update_fields=["version"])
    assert raw_details(row) == raw
    # Recognized tenant envelopes remain readable regardless of optional mode.
    settings.PII_ENCRYPTION_ENABLED = True
    assert json.loads(EventPayeeRevision.objects.get(pk=row.pk).details)["account_number"] == "00123456"
    settings.PII_ENCRYPTION_ENABLED = False
    assert json.loads(EventPayeeRevision.objects.get(pk=row.pk).details)["account_number"] == "00123456"


def test_mandatory_bulk_plaintext_and_raw_sql_are_rejected(finance_rows):
    _, owner, obligation = finance_rows
    row = payee(obligation, owner)
    with pytest.raises(RuntimeError):
        EventPayeeRevision.objects.filter(pk=row.pk).update(details="plaintext")
    with pytest.raises(RuntimeError):
        EventPayeeRevision.objects.bulk_update([row], ["details"])
    with pytest.raises(RuntimeError):
        EventPayeeRevision.objects.bulk_create([row])
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("UPDATE payments_eventpayeerevision SET details='plaintext' WHERE id=%s", [row.pk])
    assert raw_details(row).startswith("pii:gcm:v1:")


def test_mandatory_write_inside_domain_transaction_requires_preparation_without_broker_io(finance_rows, monkeypatch):
    space, owner, obligation = finance_rows
    with pytest.raises(PiiKeyUnavailable), transaction.atomic():
        payee(obligation, owner)
    prepared = prepare_tenant_key(space.pk)
    def forbidden(*args, **kwargs):
        raise AssertionError("broker I/O inside domain transaction")
    monkeypatch.setattr("apps.encryption.services.configured_broker", forbidden)
    monkeypatch.setattr("apps.encryption.services.broker_for_backend", forbidden)
    with tenant_key_context(prepared), transaction.atomic():
        row = payee(obligation, owner)
        assert json.loads(EventPayeeRevision.objects.get(pk=row.pk).details)["account_number"] == "00123456"
    assert raw_details(row).startswith("pii:gcm:v1:")


def test_mandatory_rollback_and_referenced_key_retirement_refuse_plaintext_or_key_loss(finance_rows):
    space, owner, obligation = finance_rows
    row = payee(obligation, owner)
    with pytest.raises(ValidationError):
        write_legacy_values(row, {"details": "plaintext"})
    key = MakerspaceEncryptionKey.objects.get(makerspace=space, status="active")
    with pytest.raises(PiiKeyUnavailable):
        disable_dek(space.pk, key.version)
    with pytest.raises(DatabaseError), transaction.atomic():
        MakerspaceEncryptionKey.objects.filter(pk=key.pk).update(status="disabled")
    assert MakerspaceEncryptionKey.objects.get(pk=key.pk).status == "active"


def test_prepared_mandatory_write_obeys_tenant_maintenance_fence(finance_rows):
    space, owner, obligation = finance_rows
    prepared = prepare_tenant_key(space.pk)
    admin = get_user_model().objects.create_superuser(username="g1-maintainer", password="fixture-pass")
    close_makerspace(space.pk, "enable_transition", admin.pk)
    with tenant_key_context(prepared), pytest.raises(PiiWriteFenced), transaction.atomic():
        payee(obligation, owner)


def test_django_migration_state_has_no_addon_model_drift(monkeypatch):
    from django.apps import apps
    from apps.makerspaces.models import Makerspace, default_enabled_modules
    # tests/conftest.py swaps this default for an all-modules lambda; compare the real model.
    monkeypatch.setattr(Makerspace._meta.get_field("enabled_modules"), "default", default_enabled_modules)
    # The same conftest swap applies to enabled_features (capabilities default).
    from apps.makerspaces.capabilities import default_enabled_features
    monkeypatch.setattr(Makerspace._meta.get_field("enabled_features"), "default", default_enabled_features)
    from django.db.migrations.autodetector import MigrationAutodetector
    from django.db.migrations.loader import MigrationLoader
    from django.db.migrations.state import ProjectState
    loader = MigrationLoader(None)
    changes = MigrationAutodetector(loader.project_state(), ProjectState.from_apps(apps)).changes(graph=loader.graph)
    assert not ({"events", "payments", "event_reimbursements", "accounts", "makerspaces"} & changes.keys()), changes
