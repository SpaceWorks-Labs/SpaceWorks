import time
from types import SimpleNamespace

import pytest

from apps.storage_capabilities.budget import checkpoint, client_options, storage_budget
from apps.storage_capabilities.chunks import FreeSweep
from apps.storage_capabilities.contracts import CapabilityError
from apps.storage_capabilities.runtime import configured_contracts


class Tenants:
    def __init__(self, ids):
        self.ids = ids
    def filter(self, **kwargs):
        return Tenants([pk for pk in self.ids if pk >= kwargs["pk__gte"]])
    def __getitem__(self, part):
        return [SimpleNamespace(pk=pk) for pk in self.ids[part]]
    def iterator(self, **kwargs):
        return iter(SimpleNamespace(pk=pk) for pk in self.ids)


def test_free_window_persists_cursor_and_advances_over_skipped_tenant(settings):
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "free"
    summary = {}
    window = FreeSweep(summary, None)
    assert window.batch_size(1000) == 5
    assert [row.pk for row in window.makerspaces(Tenants([2, 5, 9]))] == [2]
    window.finish_page(2, [10, 11], True)
    assert summary["next_cursor"] == {"makerspace_id": 2, "evidence_after": 11}
    window.skip(2)
    assert summary["next_cursor"] == {"makerspace_id": 3, "evidence_after": 0}


@pytest.mark.parametrize("profile", ["full", None])
def test_full_profile_ignores_all_free_limits_and_cursors(settings, profile):
    if profile is None:
        if hasattr(settings, "SPACEWORKS_DEPLOYMENT_PROFILE"):
            del settings.SPACEWORKS_DEPLOYMENT_PROFILE
    else:
        settings.SPACEWORKS_DEPLOYMENT_PROFILE = profile
    settings.FREE_MAX_PROMOTION_BYTES = 1
    summary = {}
    window = FreeSweep(summary, {"malformed-free-cursor": True})
    assert window.batch_size(1000) == 1000
    assert len(list(window.makerspaces(Tenants([2, 5, 9])))) == 3
    assert "next_cursor" not in summary
    with storage_budget(deadline=0, check_active=lambda: False):
        checkpoint()
        assert client_options() == {}


def test_free_budget_and_guard_loss_refuse_before_effects(settings):
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "free"
    with pytest.raises(CapabilityError, match="budget_exhausted"):
        with storage_budget(deadline=time.monotonic(), check_active=lambda: True):
            pass
    with pytest.raises(CapabilityError, match="attempt_fenced"):
        with storage_budget(deadline=time.monotonic() + 20, check_active=lambda: False):
            pass
    with storage_budget(deadline=time.monotonic() + 20, check_active=lambda: True):
        options = client_options()
        assert options["read_timeout"] <= 3
        assert options["retries"]["total_max_attempts"] == 1


@pytest.mark.parametrize("mode,profile", [("managed", "full"), ("managed", "free"), ("host", "free")])
def test_new_managed_and_free_profiles_require_explicit_storage_contract(settings, mode, profile):
    settings.SPACEWORKS_DEPLOYMENT_MODE = mode
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = profile
    settings.STORAGE_CAPABILITIES_FILE = ""
    with pytest.raises(CapabilityError, match="file_required"):
        configured_contracts()
