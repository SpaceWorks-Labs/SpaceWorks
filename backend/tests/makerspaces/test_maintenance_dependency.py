"""Machine maintenance needs the machines module its every surface belongs to (#97)."""

import pytest
from django.core.exceptions import ValidationError

from apps.makerspaces.capabilities import prune_features, validate_capabilities
from apps.makerspaces.models import Makerspace
from apps.makerspaces.module_install import install_module, uninstall_module
from apps.makerspaces.module_registry import core_module_keys


def test_machine_maintenance_is_refused_without_machines():
    with pytest.raises(ValidationError):
        validate_capabilities(sorted(core_module_keys()), ["machines.maintenance"])
    modules, features = validate_capabilities(sorted(core_module_keys() | {"machines"}), ["machines.maintenance"])
    assert "machines.maintenance" in features


@pytest.mark.django_db
def test_uninstalling_machines_drops_the_switch_and_keeps_it_off_on_reinstall():
    space = Makerspace.objects.create(
        name="Maintenance only", slug="maintenance-dependency",
        enabled_modules=sorted(core_module_keys()), enabled_features=[],
    )
    install_module(space, "machines")
    space.enabled_features = ["machines.maintenance"]
    space.save(update_fields=["enabled_features"])
    assert uninstall_module(space, "machines") == ["machines"]
    space.refresh_from_db()
    assert "machines.maintenance" not in space.enabled_features
    install_module(space, "machines")
    space.refresh_from_db()
    assert "machines.maintenance" not in space.enabled_features
    assert prune_features(["machines.maintenance"], core_module_keys())[1] == ["machines.maintenance"]
