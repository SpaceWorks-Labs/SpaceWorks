from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from apps.events.submissions.errors import SubmissionError
from apps.events.submissions.quota import reserve, charge, release_after_cleanup, MANAGED_ALLOWANCE


def usage(**patch):
    values = dict(budget_bytes=100, used_bytes=0, reserved_bytes=0, save=Mock())
    return SimpleNamespace(**{**values, **patch})


def rows():
    result = Mock()
    result.filter.return_value = result
    result.count.return_value = 0
    result.aggregate.return_value = {"reserved": 0, "charged": 0}
    return result


def test_event_pool_is_decimal_25gb_and_does_not_intersect_ordinary_1gib_pool():
    assert MANAGED_ALLOWANCE == 25_000_000_000
    pool = usage(budget_bytes=MANAGED_ALLOWANCE, used_bytes=2 * 1024 ** 3)
    reserve(pool, rows(), size=80, group="archives")
    assert pool.reserved_bytes == 80
    with pytest.raises(SubmissionError):
        reserve(usage(budget_bytes=None), rows(), size=1536 * 1024 ** 2 + 1, group="resume")


def test_reserve_charge_cleanup_are_exactly_once_and_keep_canonical_difference():
    pool = usage()
    reserve(pool, rows(), size=80, group="archives")
    asset = SimpleNamespace(reserved_bytes=80, charged_bytes=0)
    charge(pool, asset, 60)
    charge(pool, asset, 60)
    assert (pool.reserved_bytes, pool.used_bytes) == (20, 60)
    release_after_cleanup(pool, asset, final_deleted=False)
    assert (pool.reserved_bytes, pool.used_bytes) == (0, 60)
    release_after_cleanup(pool, asset, final_deleted=True)
    release_after_cleanup(pool, asset, final_deleted=True)
    assert (pool.reserved_bytes, pool.used_bytes) == (0, 0)


def test_cap_refusal_does_not_change_usage_or_sign_storage():
    pool = usage()
    with pytest.raises(SubmissionError):
        reserve(pool, rows(), size=101, group="archives")
    assert pool.reserved_bytes == 0
    pool.save.assert_not_called()
