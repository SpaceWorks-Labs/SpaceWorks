from tests.account_split.sweep_helpers import (
    create_test_user as _create_test_user,
)
from datetime import timedelta
import hashlib
from pathlib import Path
import shutil
import subprocess
import tarfile
from types import SimpleNamespace
import uuid

import pytest

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import connections
from django.db.backends.base.base import BaseDatabaseWrapper
from django.test import SimpleTestCase
from django.utils import timezone

from apps.backup import archive_builder
from apps.backup.models import BackupArchive
from apps.backup.main_projection_registry import (
    AUTO_CREATED_M2M_TABLES,
    RowDisposition,
    table_rules,
)
from apps.backup.projection_databases import restore_dump, temporary_database
from apps.events.models import Event, EventRegistration
from apps.inventory.models import InventoryProduct
from apps.makerspaces.models import Makerspace, MakerspaceMembership


pytestmark = pytest.mark.django_db(transaction=True)


class _EveryDatabase(frozenset):
    """A `databases` allow-set that also admits aliases created after setup.

    Iteration still yields only the real aliases, so Django's teardown flushes
    exactly the databases it created.
    """

    def __contains__(self, alias):
        return True


def _guarded_test_case():
    """The TestCase whose undeclared-database guard is currently installed.

    Django closes over the test class when it patches `ensure_connection`, and
    that class attribute is the only place the allow-set can be widened.
    """
    patched = BaseDatabaseWrapper.ensure_connection
    for cell in patched.__closure__ or ():
        value = cell.cell_contents
        if isinstance(value, type) and issubclass(value, SimpleTestCase):
            return value
    return None


@pytest.fixture
def allow_projection_databases():
    """Let the readable-main projection open its short-lived databases.

    Django rejects connections to aliases that did not exist when the test class
    was set up, which is the right default. This projection creates, registers
    and drops a real database mid-test, and `databases="__all__"` cannot express
    that because it is snapshotted at setup. The allow-set is widened for the
    duration and restored before class teardown unwraps the guard.
    """
    case = _guarded_test_case()
    if case is None:
        yield
        return
    original = case.databases
    case.databases = _EveryDatabase(original)
    try:
        yield
    finally:
        case.databases = original

PLATFORM = "age1platform-e3"


def _archive():
    return BackupArchive.objects.create(
        scope=BackupArchive.Scope.DEPLOYMENT,
        object_key=f"backup-archives/deployment/{uuid.uuid4()}.tar.age",
        expires_at=timezone.now() + timedelta(days=1),
    )


def _prepare(monkeypatch, settings):
    monkeypatch.setenv("SPACEWORKS_OCI_DIGEST", "sha256:" + "a" * 64)
    settings.BACKUP_AGE_RECIPIENT = PLATFORM
    require_binary = archive_builder._require_binary
    monkeypatch.setattr(
        archive_builder,
        "_require_binary",
        lambda command: None if command == "age" else require_binary(command),
    )
    monkeypatch.setattr(
        archive_builder,
        "_storage_modes",
        lambda: {"private": "versioned", "public_image": "versioned"},
    )
    commands = []
    real_run = archive_builder.subprocess.run

    def fake_age(command, **kwargs):
        if command[0] != "age":
            return real_run(command, **kwargs)
        commands.append(command)
        output = Path(command[command.index("-o") + 1])
        payload = kwargs.get("input")
        if payload is None:
            shutil.copyfile(command[-1], output)
        else:
            output.write_bytes(b"sealed:" + hashlib.sha256(payload).digest())
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(archive_builder.subprocess, "run", fake_age)
    return commands


def _authority_memberships(user):
    group = Group.objects.create(name=f"e3-group-{uuid.uuid4()}")
    content_type = ContentType.objects.get(
        app_label=InventoryProduct._meta.app_label,
        model=InventoryProduct._meta.model_name,
    )
    permission = Permission.objects.create(
        name="E3 retained permission",
        codename=f"e3_retained_{uuid.uuid4().hex}",
        content_type=content_type,
    )
    group.permissions.add(permission)
    user.groups.add(group)
    user.user_permissions.add(permission)
    return group, permission


def test_every_auto_created_m2m_table_has_an_explicit_disposition():
    discovered = {
        model._meta.db_table
        for model in django_apps.get_models(include_auto_created=True)
        if model._meta.auto_created and model._meta.managed
    }

    assert discovered == set(AUTO_CREATED_M2M_TABLES)
    assert all(
        disposition == RowDisposition.RETAIN_GLOBAL and predicate is None
        for disposition, predicate in AUTO_CREATED_M2M_TABLES.values()
    )
    assert {
        rule.model._meta.db_table
        for rule in table_rules()
        if rule.model._meta.auto_created
    } == discovered


def test_deployment_archive_is_one_platform_readable_component_with_every_space(
    allow_projection_databases,
    monkeypatch, settings, tmp_path
):
    """P1b: superadmin is always on, so nothing is excluded and the build succeeds."""
    first = Makerspace.objects.create(name="First E3", slug="first-e3")
    second = Makerspace.objects.create(name="Second E3", slug="second-e3")
    user = _create_test_user(username="deployment-global-e3")
    group, permission = _authority_memberships(user)
    MakerspaceMembership.objects.create(
        makerspace=first,
        user=user,
        assigned_role=first.roles.get(slug="member"),
        role="custom",
    )
    product = InventoryProduct.objects.create(
        makerspace=second,
        name="Ordinary tool",
        description="every row must remain byte-for-byte represented",
        total_quantity=7,
        available_quantity=7,
    )
    event = Event.objects.create(
        makerspace=second,
        title="Hosted event",
        starts_at=timezone.now(),
        ends_at=timezone.now() + timedelta(hours=1),
    )
    registration = EventRegistration.objects.create(
        event=event,
        name="Cross-space attendee",
        email="attendee@example.test",
        registered_via_makerspace=first,
        payment_via_makerspace=first,
    )
    expected = InventoryProduct.objects.values().get(pk=product.pk)
    commands = _prepare(monkeypatch, settings)

    encrypted, manifest, tempdir, _digest = archive_builder.build_archive(_archive())
    try:
        root = Path(tempdir.name, "bundle")
        assert (root / "manifest.json").is_file()
        assert (root / "database.dump").is_file()
        assert not (root / "slices").exists()
        assert manifest["partial"] is False
        assert manifest["excluded_makerspace_ids"] == []
        assert {first.pk, second.pk} <= set(manifest["covered_makerspace_ids"])
        assert manifest["protocol_version"] == "spaceworks-lane-e-b1-v2"
        outer = [command for command in commands if "-o" in command]
        assert outer and all(
            command.count("-r") == 1 and PLATFORM in command for command in outer
        )

        with temporary_database("e3_assert") as (using, _database_name):
            restore_dump(root / "database.dump", _database_name)
            assert Makerspace.objects.using(using).filter(pk__in=[first.pk, second.pk]).count() == 2
            assert InventoryProduct.objects.using(using).values().get(pk=product.pk) == expected
            restored_user = get_user_model().objects.using(using).get(pk=user.pk)
            assert restored_user.groups.filter(pk=group.pk).exists()
            assert restored_user.user_permissions.filter(pk=permission.pk).exists()
            restored_registration = EventRegistration.objects.using(using).get(pk=registration.pk)
            assert restored_registration.registered_via_makerspace_id == first.pk
            assert restored_registration.payment_via_makerspace_id == first.pk
        with tarfile.open(encrypted) as outer_tar:
            names = set(outer_tar.getnames())
        assert "./manifest.json" in names
        assert "./database.dump" in names
        assert not any(name.startswith("./slices") for name in names)
    finally:
        tempdir.cleanup()
