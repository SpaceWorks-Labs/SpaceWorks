"""Actual row writers race ordinary registration, including reciprocal venues."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event as Signal

import pytest
from django.db import close_old_connections, transaction

from apps.events import services
from apps.events.organization_audience import OrganizationAudienceRefused
from apps.makerspaces.models import MakerspaceMembership
from apps.organizations.models import OrganizationMembership, OrganizationMakerspace
from tests.events.organization_audience_helpers import audience_fixture, direct, local
from tests.events.ticketing_helpers import open_event, signup

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("mutation", ["suspend", "deactivate", "relink", "account", "local_revoke"])
def test_registration_rereads_proof_after_concurrent_source_writer(mutation):
    _, orgs, spaces, event, _ = audience_fixture()
    user = local(spaces[0]) if mutation in ("relink", "local_revoke") else direct(orgs[0])
    held, release = Signal(), Signal()

    def writer():
        close_old_connections()
        try:
            with transaction.atomic():
                if mutation == "suspend":
                    OrganizationMembership.objects.filter(user=user).update(status="suspended")
                elif mutation == "deactivate":
                    orgs[0].__class__.objects.filter(pk=orgs[0].pk).update(is_active=False)
                elif mutation == "relink":
                    OrganizationMakerspace.objects.filter(makerspace=spaces[0]).update(relationship="affiliate")
                elif mutation == "account":
                    user.__class__.objects.filter(pk=user.pk).update(access_status="restricted")
                else:
                    MakerspaceMembership.objects.filter(user=user).update(status="revoked")
                held.set(); assert release.wait(10)
        finally:
            close_old_connections()

    def registration():
        close_old_connections()
        try:
            assert held.wait(10)
            return signup(event, user).status_code
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        writing = pool.submit(writer); assert held.wait(10)
        registering = pool.submit(registration)
        release.set()
        writing.result(timeout=15)
        assert registering.result(timeout=15) == 403
    assert not event.registrations.exists()


def test_reciprocal_registration_uses_sorted_spaces_and_has_no_deadlock():
    venue, orgs, spaces, event, _ = audience_fixture()
    other = open_event(spaces[0], "participating_organizations")
    spaces[0].enabled_features += ["events.organization_audience"]
    spaces[0].save(update_fields=["enabled_features"])
    from apps.events.models import EventOrganizer
    EventOrganizer.objects.create(event=other, organization=orgs[2])
    users = [local(spaces[0], "from-a"), local(venue, "from-c")]
    barrier = Barrier(2)

    def register(pair):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            return signup(*pair).status_code
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(register, [(event, users[0]), (other, users[1])])) == [201, 201]
