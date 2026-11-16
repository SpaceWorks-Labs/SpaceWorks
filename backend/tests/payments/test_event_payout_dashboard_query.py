"""The payout dashboard groups per currency without re-aggregating its own sums."""
import pytest

from apps.makerspaces.models import Makerspace
from apps.payments.event_payouts.dashboard import project
from tests.account_split.p1_helpers import staff
from tests.accounts.superadmin_parity_helpers import bearer

pytestmark = pytest.mark.django_db


def test_project_builds_its_query_for_an_empty_space():
    space = Makerspace.objects.create(name="Payout dash", slug="payout-dash")
    assert project(space)["currencies"] == []


def test_dashboard_route_answers_the_space_manager():
    space = Makerspace.objects.create(name="Payout dash 2", slug="payout-dash-2")
    manager = staff(space, username="payout-dash-sm", role="space_manager")[0]
    response = bearer(manager).get(f"/api/v1/admin/makerspaces/{space.pk}/event-payouts/dashboard/")
    assert response.status_code == 200, response.content
    assert response.json()["currencies"] == []


def test_project_sums_open_obligations_per_currency():
    from uuid import uuid4
    from apps.payments.event_payouts.obligation_models import EventPayoutObligation
    space = Makerspace.objects.create(name="Payout dash 3", slug="payout-dash-3")
    for amount, currency in ((500, "INR"), (250, "INR"), (900, "USD")):
        EventPayoutObligation.objects.create(
            makerspace=space, event_id_snapshot=1, event_title_snapshot="Hack", source_uuid=uuid4(),
            source_decision_revision=1, currency=currency, approved_minor=amount)
    rows = {row["currency"]: row for row in project(space)["currencies"]}
    assert rows["INR"]["approved_minor"] == 750 and rows["INR"]["paid_minor"] == 0
    assert rows["INR"]["approved_unpaid_minor"] == 750 and rows["USD"]["ageing_0_7_minor"] == 900
