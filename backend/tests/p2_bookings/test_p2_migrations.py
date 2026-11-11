"""The hand-written Phase 2 migrations must match the model state exactly."""
import pytest
from django.apps import apps
from django.db.migrations.autodetector import MigrationAutodetector
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.state import ProjectState

pytestmark = pytest.mark.django_db


def _pending():
    loader = MigrationLoader(None, ignore_no_migrations=True)
    changes = MigrationAutodetector(loader.project_state(), ProjectState.from_apps(apps)).changes(graph=loader.graph)
    return {label: [op.describe() for migration in migrations for op in migration.operations]
            for label, migrations in changes.items()}


def test_bookings_migrations_match_models():
    pending = _pending()
    assert pending.get("bookings") is None, pending


def test_makerspaces_default_on_has_its_migration():
    ops = _pending().get("makerspaces") or []
    assert not [op for op in ops if "booking_requester_notifications_enabled" in op], ops
