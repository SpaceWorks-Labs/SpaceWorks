"""Local diagnostic: no missing migrations once BOTH conftest field-default patches are undone.

The shared `tests/fixed_roles/test_smoke_migrations.py` restores only `enabled_modules`,
while the root conftest also patches `enabled_features` with a lambda, so that test fails
on every branch. This restores both and must find nothing to migrate.
"""
import io

import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_no_missing_migrations_with_production_defaults():
    from apps.makerspaces.capabilities import default_enabled_features
    from apps.makerspaces.models import Makerspace, default_enabled_modules
    modules = Makerspace._meta.get_field("enabled_modules")
    features = Makerspace._meta.get_field("enabled_features")
    saved = modules.default, features.default
    modules.default, features.default = default_enabled_modules, default_enabled_features
    out = io.StringIO()
    try:
        call_command("makemigrations", "--check", "--dry-run", stdout=out)
    finally:
        modules.default, features.default = saved


@pytest.mark.django_db
def test_system_checks_pass(settings):
    from cryptography.fernet import Fernet
    # The isolated runner exports no PII_MASTER_KEY; encryption.E001 is a deployment check.
    settings.PII_MASTER_KEY = settings.PII_MASTER_KEY or Fernet.generate_key().decode()
    call_command("check", "--fail-level", "ERROR")
