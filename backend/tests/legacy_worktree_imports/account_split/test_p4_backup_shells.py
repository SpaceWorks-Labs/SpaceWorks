import pytest as _legacy_pytest

_legacy_pytest.skip('Not in release 0.12.0: apps.backup.main_projection_inverse, apps.backup.slice_merge_cleanup, apps.backup.slice_merge_database, apps.backup.slice_merge_staging (+8 more)', allow_module_level=True)

import json
from types import SimpleNamespace

import pytest
from django.db import connection, transaction

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.backup.main_projection_inverse import boundary_deltas
from apps.backup.raw_projection import fixture_payload, raw_records
from apps.backup.slice_merge_cleanup import drop_staging_schema
from apps.backup.slice_merge_database import merge_role, merge_schema_name, provision_merge_role
from apps.backup.slice_merge_staging import stage_group, apply_staged, verify_staged_rows
from apps.backup.slice_merge_types import SliceMergeError
from apps.backup.slice_rows import SLICE_ROW_SPECS
from apps.backup.staff_shells import SHELL_TIMESTAMP, shell_fixture
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.makerspaces.staff_retirement import shell_values
from tests.backup.test_slice_merge_database_e8 import _merging_component
from tests.backup.conftest import installed_producer_capability  # noqa: F401
from .p1_helpers import staff
from .p4_auth_helpers import staff_auth_history

pytestmark = pytest.mark.django_db(transaction=True)


def test_producer_reconstruction_exception_cannot_target_served_database():
    from apps.backup.staff_reconstruction import reconstruction_context
    from apps.backup.recipient_selection import BackupBuildError
    with pytest.raises(BackupBuildError):
        with reconstruction_context("default"):
            pytest.fail("The live database cannot enter the producer's reconstruction context.")


def test_registered_username_fence_cannot_be_substituted():
    from apps.backup.staff_shell_fences import staff_username_fences, validate_supplemental_fence
    from apps.backup.outer_reservation_validation import _bind_rules
    from uuid import uuid4
    space = Makerspace.objects.create(name="Fence staff", slug="p4-staff-fence")
    staff(space)
    component = str(uuid4())
    fences = staff_username_fences("default", {space.pk: component})
    assert len(fences) == 1 and fences[0]["columns"] == ["username"]
    validate_supplemental_fence(fences[0])
    _bind_rules([], [], fences, [], {component})
    with pytest.raises(ValueError):
        _bind_rules([], [], [{**fences[0], "table": "audit_auditlog"}], [], {component})


def test_ordinary_connection_cannot_reverse_a_retired_staff_shell():
    from django.db import DatabaseError
    space = Makerspace.objects.create(name="Guard staff", slug="p4-staff-guard")
    operator, membership = staff(space)
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('app.account_retirement_makerspace_id', %s, true)", [str(space.pk)])
        User.objects.filter(pk=operator.pk).update(**shell_values(operator.pk, SHELL_TIMESTAMP))
        membership.delete()
    with pytest.raises(DatabaseError), transaction.atomic():
        User.objects.filter(pk=operator.pk).update(staff_makerspace=space, retired_at=None, is_active=True)


@pytest.mark.parametrize("failure", ["", "tampered", "wrong_component"])
def test_only_exact_shell_can_be_reversed_by_owning_restore_component(tmp_path, failure):
    space = Makerspace.objects.create(pk=800009 if failure == "wrong_component" else 800008, name="Shell restore", slug="p4-shell-restore")
    operator, membership = staff(space, email="shell-owner@example.test", display_name="Original staff")
    inverse = next(item for item in boundary_deltas(space.pk) if item["model"] == "accounts.User")
    member_fixture = fixture_payload(MakerspaceMembership,
        raw_records(MakerspaceMembership.objects.filter(pk=membership.pk), MakerspaceMembership))
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('app.account_retirement_makerspace_id', %s, true)", [str(space.pk)])
        User.objects.filter(pk=operator.pk).update(**shell_values(operator.pk, SHELL_TIMESTAMP))
        membership.delete()
    if failure == "tampered":
        User.objects.filter(pk=operator.pk).update(display_name="unexpected occupied account")
    operation, component = _merging_component()
    rows = tmp_path / "rows"
    rows.mkdir()
    for label in SLICE_ROW_SPECS:
        payload = member_fixture if label == "makerspaces.MakerspaceMembership" else []
        (rows / f"{label.lower().replace('.', '_')}.json").write_text(json.dumps(payload), encoding="utf-8")
    (rows / "external_references.json").write_text("[]", encoding="utf-8")
    inverse_root = tmp_path / "inverse"
    inverse_root.mkdir()
    (inverse_root / "boundary-deltas.json").write_text(json.dumps([inverse]), encoding="utf-8")
    provision_merge_role()
    schema = merge_schema_name(operation.operation_id, [component.component_id])
    group = stage_group(schema, [SimpleNamespace(component=component, root=tmp_path)])
    try:
        if failure:
            with pytest.raises(SliceMergeError):
                apply_staged(group, operation.operation_id)
        else:
            with pytest.raises(SliceMergeError), transaction.atomic():
                with connection.cursor() as cursor, merge_role(
                    cursor, operation.operation_id, component.component_id, schema,
                ):
                    cursor.execute("UPDATE accounts_user SET email = %s WHERE id = %s",
                                   ["shell-owner@example.test", operator.pk])
            apply_staged(group, operation.operation_id)
            verify_staged_rows(group)
            operator.refresh_from_db()
            assert operator.staff_makerspace_id == space.pk and operator.retired_at is None
            assert operator.email == "shell-owner@example.test" and operator.display_name == "Original staff"
    finally:
        drop_staging_schema(schema)


@pytest.mark.usefixtures("installed_producer_capability")
def test_full_archive_readable_main_scrubs_staff_but_keeps_signed_auth_actor(
    allow_projection_databases, monkeypatch, settings,
):
    from apps.accounts.models import UserMFA
    from apps.backup import archive_builder
    from apps.backup.projection_databases import temporary_database, restore_dump
    from apps.audit.verification import classify_audit_row, AuditMacStatus
    from tests.audit_batch_helpers import MemoryAnchorSink, activate_and_seal
    from tests.backup import test_compound_archive_e3 as e3
    from pathlib import Path
    import tarfile
    import uuid

    settings.AUDIT_ATTESTATION_DEPLOYMENT_ID = "p4-backup-staff-audit"
    space = e3._sovereign()
    operator, _ = staff(space, username="private-staff-name", email="private-staff@example.test",
                        display_name="Private Staff", phone="+15551239876")
    sink = MemoryAnchorSink()
    activate_and_seal(None, sink)
    events = staff_auth_history(operator, space, settings)
    activate_and_seal(None, sink)
    original = {row.pk: row.row_mac for row in events}
    e3._prepare(monkeypatch, settings)
    _archive, manifest, tempdir, _digest = archive_builder.build_archive(e3._archive())
    try:
        with temporary_database("p4_readable_staff") as (using, database_name):
            restore_dump(Path(tempdir.name, "bundle", "database.dump"), database_name)
            shell = User.objects.using(using).get(pk=operator.pk)
            assert shell.username.startswith("retired-") and shell.retired_at is not None
            assert not shell.is_active and not shell.has_usable_password()
            assert shell.staff_makerspace_id is None
            assert not any((shell.email, shell.first_name, shell.last_name, shell.display_name, shell.phone))
            assert not UserMFA.objects.using(using).filter(user_id=operator.pk).exists()
            for event in AuditLog.objects.using(using).filter(pk__in=original):
                assert event.actor_id == operator.pk and event.row_mac == original[event.pk]
                # The row MAC covers the actor ID, never its mutable display identity.
                assert classify_audit_row(event) == AuditMacStatus.ATTESTED
            fact = next(item for item in manifest["slice_components"] if item["makerspace_id"] == space.pk)
            payload = Path(tempdir.name, "p4-restored-slice")
            # e3._prepare replaces age with a local copy, retaining the real tar payload.
            with tarfile.open(Path(tempdir.name, "bundle", fact["ciphertext_path"])) as bundle:
                bundle.extractall(payload, filter="data")
            operation, component = _merging_component(using=using, makerspace_id=space.pk,
                component_id=uuid.UUID(fact["component_id"]))
            provision_merge_role(using=using)
            schema = merge_schema_name(operation.operation_id, [component.component_id])
            group = stage_group(schema, [SimpleNamespace(component=component, root=payload)], using=using)
            try:
                apply_staged(group, operation.operation_id, using=using)
                verify_staged_rows(group, using=using)
                restored = User.objects.using(using).get(pk=operator.pk)
                assert restored.staff_makerspace_id == space.pk and restored.retired_at is None
                assert restored.email == operator.email and restored.display_name == operator.display_name
                assert UserMFA.objects.using(using).filter(user_id=operator.pk).exists()
                for event in AuditLog.objects.using(using).filter(pk__in=original):
                    assert event.actor_id == operator.pk and event.row_mac == original[event.pk]
                    assert classify_audit_row(event) == AuditMacStatus.ATTESTED
            finally:
                drop_staging_schema(schema, using=using)
    finally:
        tempdir.cleanup()
