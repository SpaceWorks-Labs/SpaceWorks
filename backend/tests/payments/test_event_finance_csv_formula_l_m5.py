"""SECURITY-REVIEW L-M5: the event finance CSV neutralises spreadsheet formulas, like every other export writer.

An event title is staff-typed free text; `=HYPERLINK(...)` written raw into a CSV runs as a formula when finance
staff open it. The cell is prefixed with `'` (the shared `report_exports._export_cell` rule); numbers and plain
text are untouched.
"""
import csv
from decimal import Decimal
from io import StringIO
from types import SimpleNamespace

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.payments import views_finance
from apps.payments.reports_finance_ledger import EVENT_FIELDS
from tests.return_helpers import make_member, make_space

pytestmark = pytest.mark.django_db


def _row(title):
    row = {field: Decimal("0.00") for field in EVENT_FIELDS}
    row.update({"event_id": 7, "event": title, "currency": "INR", "income": Decimal("120.00"), "net": Decimal("-5.00")})
    return row


@pytest.fixture
def finance(monkeypatch):
    """The finance gates are covered elsewhere; this pins only what the CSV writer does with the rows."""
    space = make_space("csv-formula")
    staff = make_member("csv-formula-sm", space)
    rows = []
    monkeypatch.setattr(views_finance, "require_full_session", lambda request: None)
    monkeypatch.setattr(views_finance, "finance_space",
                        lambda request, makerspace_id: (space, SimpleNamespace(sees=lambda area: True)))
    monkeypatch.setattr(views_finance, "_event", lambda space, event_id: SimpleNamespace(pk=event_id))
    monkeypatch.setattr(views_finance, "event_finance", lambda space, view, actor, event_id: list(rows))
    return space, staff, rows


def _csv(space, staff):
    request = APIRequestFactory().get("/api/v1/finance/events/7?format=csv")
    force_authenticate(request, user=staff)
    response = views_finance.EventFinanceView.as_view()(request, makerspace_id=space.pk, event_id=7)
    assert response.status_code == 200 and response["Content-Type"].startswith("text/csv")
    return list(csv.DictReader(StringIO(response.content.decode())))


@pytest.mark.parametrize("title", ['=HYPERLINK("https://evil.example","Open")', "+1+1", "-2+3", "@SUM(A1)",
                                   "\t=1", "\r=1"])
def test_a_formula_title_is_written_as_text(finance, title):
    space, staff, rows = finance
    rows.append(_row(title))
    [written] = _csv(space, staff)
    assert written["event"] == f"'{title}"


def test_plain_titles_and_money_are_unchanged(finance):
    space, staff, rows = finance
    rows.append(_row("Maker Night"))
    [written] = _csv(space, staff)
    assert written["event"] == "Maker Night"
    assert written["income"] == "120.00" and written["net"] == "-5.00"   # numbers are not strings: never prefixed
