from importlib import import_module

from django.apps import apps
import pytest

from apps.makerspaces.models import DEFAULT_ENABLED_MODULES
from apps.makerspaces.module_profiles import EVERYTHING, profile_modules
from apps.makerspaces.platform import FEATURE_WORKFLOWS
from tests.return_helpers import make_space


pytestmark = pytest.mark.django_db
migration = import_module(
    "apps.makerspaces.migrations.0034_enable_maintenance_module"
)


def test_module_migration_is_idempotent_and_preserves_custom_flags():
    makerspace = make_space("maintenance-module-migration")
    makerspace.enabled_modules = ["custom", "machines"]
    makerspace.save(update_fields=["enabled_modules"])

    migration.enable_maintenance(apps, None)
    migration.enable_maintenance(apps, None)
    makerspace.refresh_from_db()

    assert makerspace.enabled_modules == ["custom", "machines", "maintenance"]
    migration.disable_maintenance(apps, None)
    makerspace.refresh_from_db()
    assert makerspace.enabled_modules == ["custom", "machines"]


def test_new_makerspaces_and_platform_workflow_include_maintenance():
    makerspace = make_space("maintenance-module-default")
    # L17 (#97, #128 C-9): maintenance is no longer a module of its own but the
    # `machines.maintenance` capability under its parent, so no profile installs it.
    assert "maintenance" not in DEFAULT_ENABLED_MODULES
    assert "maintenance" not in profile_modules(EVERYTHING)
    assert "machines" in profile_modules(EVERYTHING)
    assert FEATURE_WORKFLOWS["machines.maintenance"] == ["maintenance"]
