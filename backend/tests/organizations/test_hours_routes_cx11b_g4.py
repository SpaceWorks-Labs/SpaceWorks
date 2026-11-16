"""Organization-admin reads: browser governance, no native governance authority."""
import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.bookings.models_organization_hours import OrganizationHoursAllowance, OrganizationHoursLedger
from apps.organizations.governance import MANAGE_ORGANIZATION_PROFILE
from apps.organizations.models import Organization, OrganizationMakerspace, OrganizationMembership
from tests.modules.switch_matrix_object_helpers import client_for, object_world
from tests.operations.route_support_cx11b_g4 import cycle, outsider

pytestmark = [pytest.mark.django_db, pytest.mark.area_organizations, pytest.mark.area_bookings]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native-refused"])
@pytest.mark.parametrize("key", ["bookings", "bookings.organization_bookings"])
@pytest.mark.parametrize("name", ["admin-organization-hours-bank", "admin-organization-hours-ledger"])
def test_organization_hours_read_retains_allowance_and_ledger(native, key, name):
    space, browser, _ = object_world(False)
    actor = User.objects.get(username="sx-real-object-manager")
    organization = Organization.objects.create(name="Retained partner", slug="g4-partner")
    OrganizationMakerspace.objects.create(organization=organization, makerspace=space, relationship="affiliate")
    OrganizationMembership.objects.create(organization=organization, user=actor,
                                           governance_actions=[MANAGE_ORGANIZATION_PROFILE])
    allowance = OrganizationHoursAllowance.objects.create(makerspace=space, organization=organization,
                                                          allowance_minutes=120, period="none", updated_by=actor)
    ledger = OrganizationHoursLedger.objects.create(makerspace=space, organization=organization,
        entry="grant", minutes=30, period_key="all", reason="Retained grant", actor=actor)
    client = client_for(actor, space, True) if native else browser
    kwargs = {"pk": organization.pk}
    if name.endswith("ledger"):
        kwargs["makerspace_id"] = space.pk
    url = reverse(name, kwargs=kwargs)
    foreign = outsider(native)

    def retained():
        allowance.refresh_from_db()
        ledger.refresh_from_db()
        assert (allowance.allowance_minutes, allowance.period, ledger.minutes, ledger.reason) == (120, "none", 30, "Retained grant")

    # 494: this native ledger refusal is on a makerspace_id-addressed route;
    # the global organization bank retains its separate native 403.
    native_pair = (404, "not_found") if name.endswith("ledger") else (403, "permission_denied")

    def check(response):
        retained()
        if native:
            assert response.data["code"] == native_pair[1]
        elif name.endswith("bank"):
            assert len(response.data["banks"]) == 1
            bank = response.data["banks"][0]
            assert (bank["organization_id"], bank["makerspace_id"], bank["allowance_minutes"], bank["remaining_minutes"]) == (organization.pk, space.pk, 120, 150)
        else:
            assert [(row["id"], row["minutes"], row["reason"]) for row in response.data["results"]] == [(ledger.pk, 30, "Retained grant")]
            assert "actor_name" not in response.data["results"][0]

    def off_check(response):
        retained()
        if not native and name.endswith("bank"):
            assert response.data == {"banks": []}
    # The declared global organization contract requires governance; no membership or
    # tenant staff grant supplies it. Native sessions have no organization governance.
    cycle(space, key, lambda: client.get(url), check,
          on=native_pair if native else (200, None),
          off=(200, None) if not native and name.endswith("bank") else (native_pair if native else (404, "not_found")),
          off_check=off_check, foreign=lambda: foreign.get(url), foreign_native=native)
