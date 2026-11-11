"""The capture-bound money fingerprint covers L5 rows and is unchanged for spaces without them."""

import pytest

from apps.payments import ledger_api
from apps.tenant_migration.money_digest import money_fingerprint
from tests.l5_local.helpers import setup

pytestmark = pytest.mark.django_db


def test_an_expense_or_void_after_capture_is_money_drift():
    space, manager, _payer = setup("fingerprint")
    before = money_fingerprint(space.pk)
    entry = ledger_api.record_expense(space, "general", None, "10.00", "inr", "cash", "", None, "manual", "",
                                      manager, category="rent")
    after_expense = money_fingerprint(space.pk)
    assert after_expense != before
    ledger_api.void(entry, manager, "Typo")
    assert money_fingerprint(space.pk) != after_expense


def test_a_space_without_l5_rows_keeps_its_fingerprint_shape():
    from apps.tenant_migration.money_digest_l5 import l5_money_rows

    space, _manager, _payer = setup("fingerprint-empty")
    assert l5_money_rows(space.pk) == {}
