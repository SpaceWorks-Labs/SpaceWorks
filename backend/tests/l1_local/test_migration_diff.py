"""Local helper: list what makemigrations would change, without writing (never committed)."""

import pytest
from django.apps import apps
from django.db import connection
from django.db.migrations.autodetector import MigrationAutodetector
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.state import ProjectState

pytestmark = pytest.mark.django_db


def test_show_pending_migrations():
    loader = MigrationLoader(connection, ignore_no_migrations=True)
    changes = MigrationAutodetector(loader.project_state(), ProjectState.from_apps(apps)).changes(graph=loader.graph)
    lines = [f"{app}: {op.describe()}" for app, migrations in changes.items()
             for migration in migrations for op in migration.operations]
    # The autouse conftest fixture patches these two defaults with lambdas (test-only noise).
    noise = {"Alter field enabled_modules on makerspace", "Alter field enabled_features on makerspace"}
    lines = [line for line in lines if line.split(": ", 1)[1] not in noise]
    assert not lines, "\n".join(lines)
