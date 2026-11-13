import io

import pytest
from django.core.management import call_command

from apps.makerspaces.models import Makerspace, MakerspaceRole
from apps.makerspaces.role_catalog import BUILTIN_ROLE_SLUGS


@pytest.mark.django_db
def test_no_missing_migrations():
    # The autouse conftest fixture changes BOTH capability defaults for test data only.
    # Restore their production callables before asking Django to compare model state.
    from apps.makerspaces.capabilities import default_enabled_features
    from apps.makerspaces.models import default_enabled_modules

    fields = {"enabled_modules": default_enabled_modules, "enabled_features": default_enabled_features}
    saved = {}
    for name, production in fields.items():
        field = Makerspace._meta.get_field(name)
        saved[name], field.default = field.default, production
    try:
        call_command("makemigrations", "--check", "--dry-run", stdout=io.StringIO())
    finally:
        for name, test_default in saved.items():
            Makerspace._meta.get_field(name).default = test_default


@pytest.mark.django_db
def test_new_makerspace_gets_seven_builtins():
    space = Makerspace.objects.create(name="Smoke", slug="smoke-fixed-roles")
    slugs = set(MakerspaceRole.objects.filter(makerspace=space).values_list("slug", flat=True))
    assert slugs == set(BUILTIN_ROLE_SLUGS)
