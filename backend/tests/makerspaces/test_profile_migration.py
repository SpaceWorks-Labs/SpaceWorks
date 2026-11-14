from importlib import import_module
from types import SimpleNamespace

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from apps.makerspaces.models import Makerspace


@pytest.mark.django_db
def test_timezone_backfill_uses_deployment_timezone(settings):
    settings.TIME_ZONE = "Asia/Kolkata"
    registry = MigrationExecutor(connection).loader.project_state(
        [("makerspaces", "0077_makerspace_location_profile")]).apps
    lab = Makerspace.objects.create(name="Backfilled profile", slug="profile-backfill", timezone="UTC")
    step = import_module("apps.makerspaces.migrations.0077_makerspace_location_profile")
    step.backfill_timezone(registry, SimpleNamespace(connection=connection))
    lab.refresh_from_db()
    assert lab.timezone == "Asia/Kolkata"
    assert lab.country == "" and lab.opening_hours == {}
