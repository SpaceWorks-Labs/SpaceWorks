"""SECURITY-REVIEW L-M2: a quota check by a creator that holds no other lock locks the space row first.

`check_extra_quota` counts rows and compares; two concurrent creators both counted N-1 and both passed. The
`_locked` variant takes `SELECT ... FOR UPDATE` on the makerspace row before counting, so they queue. While the
key is unlimited (the default) it neither locks nor counts, so an unlimited space pays nothing.
"""
import inspect

import pytest
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext

from apps.managed_hosting import extra_quotas as eq
from tests.open_items_0120.test_platform_credential_limits import _limit
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db
KEY = "stock_transfers_monthly"


@pytest.fixture(autouse=True)
def _self_host(settings):
    settings.PLATFORM_DOMAIN_SUFFIX = ""
    settings.MANAGED_PLANS_ENABLED = False


def _locks(queries):
    return [q["sql"] for q in queries.captured_queries if "FOR UPDATE" in q["sql"]]


def test_an_unlimited_key_neither_locks_nor_counts():
    space = make_space("lm2-free")
    with transaction.atomic(), CaptureQueriesContext(connection) as queries:
        eq.check_extra_quota_locked(space, KEY, adding=10 ** 6)
    assert _locks(queries) == []


def test_a_limited_key_locks_the_space_then_counts():
    space = make_space("lm2-limited")
    _limit(space, **{KEY: 3})
    with transaction.atomic(), CaptureQueriesContext(connection) as queries:
        eq.check_extra_quota_locked(space, KEY)
    assert len(_locks(queries)) == 1 and "makerspace" in _locks(queries)[0].lower()


def test_the_limit_still_refuses_with_the_typed_409():
    space = make_space("lm2-zero")
    _limit(space, **{KEY: 0})
    with pytest.raises(eq.ExtraQuotaReached), transaction.atomic():
        eq.check_extra_quota_locked(space, KEY)


@pytest.mark.parametrize("module, function", [
    ("apps.operations.services_transfers", "apply_stock_transfer"),
    ("apps.operations.services_stocktake_workflow", "create_stocktake"),
    ("apps.operations.views_report_schedules", "ReportScheduleListCreateView"),
    ("apps.card_designs.templates", "create_from_design"),
    ("apps.card_designs.templates", "create_from_document"),
    ("apps.card_designs.templates", "duplicate"),
    ("apps.card_designs.templates_files", "import_file"),
    ("apps.card_designs.cutouts", "request"),
])
def test_every_creator_named_by_the_review_uses_the_locked_check(module, function):
    import importlib
    source = inspect.getsource(getattr(importlib.import_module(module), function))
    assert "check_extra_quota_locked(" in source
