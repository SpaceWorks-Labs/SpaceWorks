"""Lane W proposal for C-owned tests/makerspaces/test_reconciliation_w.py.

C must install this module in its owned directory. W has not edited that path.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from django.db import close_old_connections
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.makerspaces.membership_renewal_charges import raise_renewal
from apps.makerspaces.models import MakerspaceMembership, MembershipPlan, MembershipTerm
from apps.payments.models import Payment
from tests.return_helpers import make_space, make_user


def renewal_case(suffix):
    space = make_space(f"recon-renewal-{suffix}")
    space.enabled_modules = sorted((set(space.enabled_modules) | {"membership"}) - {"payments"})
    space.enabled_features = sorted(set(space.enabled_features) | {"charges.enabled", "charges.membership"})
    space.save(update_fields=["enabled_modules", "enabled_features"])
    user = make_user(f"recon-renewal-{suffix}", access_status="active")
    membership = MakerspaceMembership.objects.create(user=user, makerspace=space, role="custom",
                                                     assigned_role=space.roles.get(slug="member"))
    plan = MembershipPlan.objects.create(makerspace=space, name="Monthly", interval="monthly",
                                         amount="10.00", currency="usd")
    now = timezone.now()
    term = MembershipTerm.objects.create(membership=membership, plan=plan,
        starts_at=now - timedelta(days=25), ends_at=now + timedelta(days=5))
    return space, membership, term


@pytest.mark.django_db
def test_stale_renewal_caller_records_one_rail_free_charge_and_audit():
    space, membership, term = renewal_case("once")
    stale = MembershipTerm.objects.get(pk=term.pk)
    assert raise_renewal(term) == "charged"
    assert raise_renewal(stale) == "skipped"
    payment = Payment.objects.get(makerspace=space, subject_type="membership_term", subject_id=term.pk)
    assert payment.provider == "unclaimed" and payment.member_id == membership.user_id
    assert stale.renewal_payment_id == payment.pk
    assert AuditLog.objects.filter(action="membership.renewal_raised", target_id=str(term.pk)).count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize("state", ["revoked", "cancelled", "deleted", "tracking_off"])
def test_renewal_reloads_lifecycle_state_before_creating_debt(state):
    space, membership, term = renewal_case(state)
    if state == "revoked":
        MakerspaceMembership.objects.filter(pk=membership.pk).update(status="revoked")
    elif state == "cancelled":
        MembershipTerm.objects.filter(pk=term.pk).update(status="cancelled")
    elif state == "deleted":
        User.objects.filter(pk=membership.user_id).update(deletion_requested_at=timezone.now(), is_active=False)
    else:
        space.enabled_features = [key for key in space.enabled_features if not key.startswith("charges.")]
        space.save(update_fields=["enabled_features"])
    assert raise_renewal(term) == "skipped"
    assert not Payment.objects.filter(subject_type="membership_term", subject_id=term.pk).exists()


@pytest.mark.django_db(transaction=True)
def test_two_renewal_writers_serialize_to_one_charge():
    space, _, term = renewal_case("race")
    barrier = Barrier(2)
    def write():
        close_old_connections()
        try:
            seed = MembershipTerm.objects.select_related("membership__makerspace", "plan").get(pk=term.pk)
            barrier.wait(timeout=10)
            return raise_renewal(seed)
        finally:
            close_old_connections()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: write(), range(2)))
    assert sorted(results) == ["charged", "skipped"]
    assert Payment.objects.filter(makerspace=space, subject_type="membership_term", subject_id=term.pk).count() == 1
    assert AuditLog.objects.filter(action="membership.renewal_raised", target_id=str(term.pk)).count() == 1

# C should additionally keep its admission/activation regression cases proving:
# - source=approval emits the owner's one welcome plus the separate staff notice;
# - staff invitation/account lifecycle never runs through community admission;
# - member revoke ends presence and invalidates only that account's tenant push devices;
# - request/invitation locks precede User when activation races account deletion.
