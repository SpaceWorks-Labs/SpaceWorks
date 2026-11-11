"""Capacity updates fence shared accounts before any promotion takes more locks."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, local

import pytest
from django.db import close_old_connections

from apps.events import organization_audience, services
from apps.events.models import EventRegistration
from apps.organizations.models import Organization, OrganizationMakerspace, OrganizationMembership
from tests.events.collab_helpers import make_staff
from tests.events.organization_audience_helpers import audience_fixture, direct
from tests.events.ticketing_helpers import event_space, open_event

pytestmark = pytest.mark.django_db(transaction=True)


def test_disjoint_audiences_promote_opposite_waiters_without_partial_account_fences(monkeypatch):
    _, orgs, _, first_event, first_manager = audience_fixture(capacity=1)
    other_space = event_space("other-promotion-venue")
    other_space.enabled_features += [organization_audience.FEATURE]
    other_space.save(update_fields=["enabled_features"])
    other_org = Organization.objects.create(name="D", slug="d")
    OrganizationMakerspace.objects.create(
        organization=other_org, makerspace=other_space, relationship="owner",
    )
    second_event = open_event(other_space, organization_audience.AUDIENCE, capacity=1)
    second_manager = make_staff(other_space)
    first_user, second_user = direct(orgs[0], "first"), direct(orgs[0], "second")
    for user in (first_user, second_user):
        OrganizationMembership.objects.create(organization=other_org, user=user, granted_actions=[])
    # Distinct space/organization roots; the account rows are the only shared locks.
    for event, users in ((first_event, (first_user, second_user)),
                         (second_event, (second_user, first_user))):
        assert [services.register(event, member=user).status for user in users] == ["registered", "waitlisted"]

    original = organization_audience.lock_admission_sources
    barrier, worker = Barrier(2), local()
    participant_ids = {first_user.pk, second_user.pk}

    def fence(event, user_ids=(), **kwargs):
        user_ids = list(user_ids)
        if not getattr(worker, "fenced", False):
            worker.fenced = True
            # Fail before taking an incomplete fence rather than waiting for a PG deadlock.
            assert participant_ids.issubset(user_ids)
            assert kwargs["include_authority"] is True
            barrier.wait(timeout=10)
        return original(event, user_ids, **kwargs)

    monkeypatch.setattr(organization_audience, "lock_admission_sources", fence)

    def increase(pair):
        close_old_connections()
        try:
            event, manager = pair
            return services.update_event(event, actor=manager, capacity=2).capacity
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(increase, pair) for pair in (
            (first_event, first_manager), (second_event, second_manager),
        )]
        assert [future.result(timeout=20) for future in futures] == [2, 2]
    for event in (first_event, second_event):
        assert event.registrations.count() == 2
        assert event.registrations.filter(status=EventRegistration.Status.REGISTERED).count() == 2
