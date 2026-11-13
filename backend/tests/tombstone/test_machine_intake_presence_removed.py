"""Run only in the real tombstone profile, not an override of settings."""
import pytest
from rest_framework.exceptions import NotFound

from apps.machines.public_intake_access import require_public_intake_available
from apps.makerspaces.models import Makerspace
from apps.separability.registry import runtime_active


@pytest.mark.django_db
def test_intake_is_unavailable_when_presence_runtime_is_removed():
    assert not runtime_active("presence")
    space = Makerspace.objects.create(name="Intake tombstone", slug="intake-tombstone")
    space.enabled_modules = sorted(set(space.enabled_modules or ()) | {"membership", "presence"})
    # This simulates an existing tenant retaining its stored switch after deployment removal.
    Makerspace.objects.filter(pk=space.pk).update(enabled_modules=space.enabled_modules)
    space.refresh_from_db()
    with pytest.raises(NotFound) as error:
        require_public_intake_available(space)
    assert error.value.detail["code"] == "machine_intake_unavailable"
