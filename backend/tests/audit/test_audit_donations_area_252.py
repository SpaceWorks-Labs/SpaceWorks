"""Decision 252 follow-up: an audit "donations" area, so Fundraising reads donation audit rows (219(e))."""
import pytest

from apps.audit import areas
from apps.audit import services as audit
from apps.makerspaces.role_catalog import ROLE_BY_SLUG
from tests.fixed_roles.helpers import staff_account
from tests.r2_superadmin_local.helpers import api, space

pytestmark = pytest.mark.django_db
URL = "/api/v1/admin/audit-logs"
DONATION_ACTIONS = ("donation.created", "donation.paid", "pledge.created")


def _seed(lab):
    for action in DONATION_ACTIONS + ("payment.recorded", "request.accepted"):
        audit.record(None, action, makerspace=lab, meta={"seed": lab.slug})


def _seen(client):
    response = client.get(URL)
    assert response.status_code == 200
    return {row["action"] for row in response.json()["results"]}


def test_donation_namespaces_are_placed_in_the_donations_area_and_finance_keeps_them():
    for action in DONATION_ACTIONS + ("sponsor.created",):
        assert areas.DONATIONS in areas.areas_for_action(action)
        assert areas.FINANCE in areas.areas_for_action(action)
    assert areas.DONATIONS not in areas.areas_for_action("payment.recorded")
    assert areas.AREA_ACTIONS[areas.DONATIONS] == (areas.A.MANAGE_DONATIONS,)
    assert areas.A.MANAGE_DONATIONS in areas.READER_ACTIONS


def test_fundraising_reads_donation_rows_only_not_other_areas():
    lab = space("aud-fundraising")
    client = api(staff_account(lab, "aud-fundraiser", "fundraising"))
    _seed(lab)
    seen = _seen(client)
    assert set(DONATION_ACTIONS) <= seen
    assert not {"payment.recorded", "request.accepted"} & seen


def test_fundraising_never_reads_another_spaces_donation_rows():
    lab, other = space("aud-fund-a"), space("aud-fund-b")
    client = api(staff_account(lab, "aud-fund-actor", "fundraising"))
    _seed(other)
    assert not set(DONATION_ACTIONS) & _seen(client)


def test_other_area_roles_do_not_gain_donation_rows_and_the_space_manager_sees_them():
    lab = space("aud-fund-roles")
    shop = api(staff_account(lab, "aud-fund-shop", "shop_manager"))
    boss = api(staff_account(lab, "aud-fund-boss", "space_manager"))
    _seed(lab)
    assert not set(DONATION_ACTIONS) & _seen(shop)
    assert set(DONATION_ACTIONS) <= _seen(boss)
    assert "manage_donations" in ROLE_BY_SLUG["fundraising"].granted_actions
