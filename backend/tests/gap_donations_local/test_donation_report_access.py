"""RP-3: finance-only access, switches, privacy (no PAN or contact ever) and the registry guards."""

import pytest

from apps.operations.org_report_scope import EXCLUDED_ORGANIZATION_REPORT_KEYS
from apps.operations.org_report_strategies import STRATEGIES
from apps.operations.report_registry import REPORT_REGISTRY
from apps.operations.report_subjects import report_action_allowed
from apps.operations.report_validation import validate_chart_spec, validate_report_definition
from apps.payments.models import Sponsor, SponsorPerk
from tests.gap_donations_local.helpers import (
    KEYS, PAN, analytics, campaign, client, export_csv, finance_staff, paid_gift, report_space, staff, switch,
)
from tests.l18_local.helpers import tax_ready

pytestmark = pytest.mark.django_db
ALL = ("finance.recurring_donations", "finance.sponsors")
SECRETS = ("pan", "donor_", "contact_", "access_secret", "manage_secret", "address", "email", "phone", "note")


def test_every_donations_report_is_registered_finance_only_and_tenant_local():
    for key in KEYS:
        definition = REPORT_REGISTRY[key]
        validate_report_definition(definition)
        assert definition.required_action == "view_finance"
        assert not definition.deployment_aggregate and not definition.platform_only
        assert key in EXCLUDED_ORGANIZATION_REPORT_KEYS and key not in STRATEGIES
        validate_chart_spec(definition.chart_spec, definition.fields)
        # `donor_count` is an aggregate count of distinct givers, never a donor's identity.
        assert not any(marker in field for field in definition.fields if field != "donor_count"
                       for marker in SECRETS), key
    assert REPORT_REGISTRY["donations-campaign-progress"].required_feature == "finance.donations"
    assert REPORT_REGISTRY["donations-pledges"].required_feature == "finance.recurring_donations"
    assert REPORT_REGISTRY["donations-sponsor-perks"].required_feature == "finance.sponsors"
    assert REPORT_REGISTRY["finance-donations"].required_feature == "finance.ledger"


@pytest.mark.parametrize("role", ["event_manager", "inventory_manager", "machine_manager", "booking_manager"])
def test_area_managers_never_see_donations_reports(role):
    space, manager, donor = report_space(f"rp3-deny-{role[:5]}", *ALL)
    other = staff(f"rp3-deny-{role[:5]}", space, role)
    catalog = analytics(other, space, "donations-campaign-progress")
    assert catalog.status_code in (403, 404)
    for key in KEYS:
        assert not report_action_allowed(other, REPORT_REGISTRY[key], space.pk)
        assert analytics(other, space, key).status_code in (403, 404)


def test_space_manager_and_finance_staff_read_and_export_every_donations_report():
    space, manager, donor = report_space("rp3-allow", *ALL)
    finance = finance_staff("rp3-allow", space)
    # The Fundraising role (decision 242(m)) reaches the three donations reports through
    # `manage_donations`; the ledger area `finance-donations` stays `view_finance` (Space Manager) only.
    for user, wanted in ((manager, KEYS), (finance, KEYS[:3])):
        keys = {row["key"] for row in client(user).get(f"/api/v1/admin/makerspace/{space.pk}/reports/catalog").json()["results"]}
        assert set(wanted) <= keys
        for key in wanted:
            assert analytics(user, space, key).status_code == 200, key
            response, _body = export_csv(user, space, key)
            assert response.status_code == 200, key


@pytest.mark.parametrize("key,feature", [
    ("donations-campaign-progress", "finance.donations"),
    ("donations-pledges", "finance.recurring_donations"),
    ("donations-sponsor-perks", "finance.sponsors"),
    ("finance-donations", "finance.ledger"),
])
def test_each_report_follows_its_own_switch(key, feature):
    space, manager, donor = report_space(f"rp3-sw-{key[-6:]}", *ALL)
    assert analytics(manager, space, key).status_code == 200
    switch(space, feature, on=False)
    assert analytics(manager, space, key).status_code == 404
    entry = next((row for row in client(manager).get(f"/api/v1/admin/makerspace/{space.pk}/reports/catalog").json()["results"]
                  if row["key"] == key), None)
    assert entry is None or entry["available"] is False
    switch(space, feature)
    assert analytics(manager, space, key).status_code == 200


# The gift is settled and the PAN encrypted through on_commit hooks, so this needs real commits.
@pytest.mark.django_db(transaction=True)
def test_no_pan_donor_or_sponsor_contact_ever_reaches_an_export():
    space, manager, donor = report_space("rp3-private", *ALL)
    tax_ready(space)
    laser = campaign(space)
    paid_gift(space, manager, donor, "900.00", campaign=laser.pk, wants_tax_receipt=True, donor_pan=PAN,
              donor_address="2 Hill Rd", note="In memory of Ada")
    sponsor = Sponsor.objects.create(makerspace=space, name="Acme Robotics", contact_name="Rita Contact",
                                     contact_email="rita@acme.example", contact_phone="+919900000000")
    SponsorPerk.objects.create(makerspace=space, sponsor=sponsor, description="Logo on banner")
    secrets = (PAN, PAN[-4:] + "\n", "2 Hill Rd", "In memory of Ada", donor.email, donor.username,
               "Rita Contact", "rita@acme.example", "+919900000000")
    for key in KEYS:
        response, body = export_csv(manager, space, key)
        assert response.status_code == 200, key
        leaked = [value for value in secrets if value and value in body]
        assert not leaked, f"{key} leaked {leaked}"
        preview = analytics(manager, space, key).content.decode()
        assert not [value for value in secrets if value in preview], key


def test_superadmin_reaches_every_donations_report():
    from apps.accounts.models import User
    from apps.operations.reports import report_data

    space, manager, donor = report_space("rp3-root", *ALL)
    root = User.objects.create_superuser("rp3-root-admin", email="root@rp3.test", password="x" * 20)
    for key in KEYS:
        assert report_action_allowed(root, REPORT_REGISTRY[key], space.pk)
        assert report_data(key, space.pk, actor=root)["rows"][0] == list(REPORT_REGISTRY[key].fields)


def test_donations_reports_never_run_deployment_wide():
    from apps.operations.report_registry import DEPLOYMENT_AGGREGATE_REPORT_KEYS
    from apps.operations.reports import ReportNotFound, report_data

    for key in KEYS:
        assert key not in DEPLOYMENT_AGGREGATE_REPORT_KEYS
        with pytest.raises(ReportNotFound):
            report_data(key, None)
