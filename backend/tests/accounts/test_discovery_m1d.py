"""Account-only ownership and newly arriving participation cannot escape Stage A."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from apps.accounts import account_deletion as deletion
from apps.accounts.account_deletion_discovery import tenant_ids
from apps.makerspaces.models import MakerspaceMembership, MembershipRequest
from apps.organizations.models import Organization, OrganizationMembership
from tests.accounts import deletion_factories as f
from tests.accounts.test_obligation_races_m1d import connected
from tests.accounts.test_support_m1d import account, m1d_config, proven

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("kind", ["request", "booking", "registration", "payment", "legacy_service", "application"])
def test_account_only_tenant_is_included_without_a_membership(kind):
    user, tenant = account(), f.space()
    if kind == "request":
        f.request(user, tenant)
    elif kind == "booking":
        f.booking(user, tenant, status="completed")
    elif kind == "registration":
        f.registration(user, tenant, status="cancelled")
    elif kind == "payment":
        f.payment(user, tenant, status="paid_offline")
    elif kind == "legacy_service":
        f.service_job(user, tenant, status="collected", legacy=True)
    else:
        MembershipRequest.objects.create(user=user, makerspace=tenant, state="requested")
    assert not MakerspaceMembership.objects.filter(user=user).exists()
    assert tenant_ids(user) == {tenant.pk}
    assert deletion.request_deletion(proven(user))["deleted_at"]
    if kind == "application":
        assert MembershipRequest.objects.get(user=user).state == "canceled"


@pytest.mark.parametrize("growing", ["tenant", "organization"])
def test_real_concurrent_participation_growth_rolls_back_then_rediscovers(growing, monkeypatch):
    user, old, added = account(), f.space(), f.space()
    f.request(user, old)
    req = proven(user)
    discovered, continue_to_locks = Event(), Event()
    real_gates = deletion._gates
    attempts = []

    def pause_first_snapshot(ids):
        attempts.append(set(ids))
        if len(attempts) == 1:
            discovered.set()
            assert continue_to_locks.wait(timeout=7)
        return real_gates(ids)

    monkeypatch.setattr(deletion, "_gates", pause_first_snapshot)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(connected, lambda: deletion.request_deletion(req))
        try:
            assert discovered.wait(timeout=5)
            if growing == "tenant":
                f.request(user, added)
            else:
                organization = Organization.objects.create(name="New participation", slug="m1d-new-org")
                membership = OrganizationMembership.objects.create(organization=organization, user=user)
        finally:
            continue_to_locks.set()
        assert pending.result(timeout=15)["deleted_at"]
    assert len(attempts) == 2
    if growing == "tenant":
        assert attempts == [{old.pk}, {old.pk, added.pk}]
    else:
        membership.refresh_from_db()
        assert membership.status == "suspended"


def test_continuously_growing_tenant_set_returns_retry_without_partial_departure(monkeypatch):
    user = account()
    req = proven(user)
    calls = []

    def changes(user):
        calls.append(user.pk)
        return set() if len(calls) % 2 else {999999}

    monkeypatch.setattr(deletion, "tenant_ids", changes)
    with pytest.raises(deletion.DeletionRetry) as exc:
        deletion.request_deletion(req)
    assert len(calls) == 6 and exc.value.status_code == 503
    assert exc.value.detail["code"] == "deletion_retry"
    user.refresh_from_db()
    assert user.is_active and user.deletion_requested_at is None
