"""The built-in CNC Router keeps its proper name (0017 used to title-case it to "Cnc Router")."""
import importlib

import pytest
from django.apps import apps as django_apps

from apps.machines.models import MachineType

fix = importlib.import_module("apps.machines.migrations.0034_builtin_cnc_router_name")


@pytest.mark.django_db
def test_migrated_builtin_types_use_their_proper_names():
    names = dict(MachineType.objects.filter(makerspace__isnull=True, is_builtin=True).values_list("slug", "name"))
    assert names["cnc_router"] == "CNC Router"
    assert names["cnc_mill"] == "CNC Mill"


@pytest.mark.django_db
def test_fix_renames_only_the_generated_name():
    row = MachineType.objects.get(makerspace__isnull=True, slug="cnc_router")
    MachineType.objects.filter(pk=row.pk).update(name="Cnc Router")
    fix.forward(django_apps, None)
    assert MachineType.objects.get(pk=row.pk).name == "CNC Router"
    MachineType.objects.filter(pk=row.pk).update(name="Big router")
    fix.forward(django_apps, None)
    assert MachineType.objects.get(pk=row.pk).name == "Big router"
