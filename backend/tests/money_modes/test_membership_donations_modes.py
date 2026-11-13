"""#184 matrix, membership joining (G8) and donations / sponsors (G10) in each mode."""

from decimal import Decimal

import pytest

from apps.makerspaces import membership_services
from apps.makerspaces.models import MakerspaceMembership, MembershipTerm
from tests.makerspaces.test_membership_admission_matrix import _application, _setup
from tests.makerspaces.test_membership_j1 import member_role
from tests.money_modes.helpers import FREE, MODES, ONLINE, assert_mode_outcome, charges, fake_provider, set_mode

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("timing", ["before_activation", "after_activation"])
@pytest.mark.parametrize("mode", MODES)
def test_a_paid_plan_admits_in_every_mode(mode, timing, monkeypatch):
    makerspace, actor, applicant, plan, _ = _setup(paid=True, timing=timing, joining_fee=Decimal("5.00"))
    set_mode(makerspace, "membership", mode)
    checkout = fake_provider(monkeypatch) if mode == ONLINE else None
    row = _application(makerspace, applicant)
    membership_services.approve_request(actor, row, member_role(makerspace))
    row.refresh_from_db()
    payment = assert_mode_outcome(mode, charges(makerspace, "membership_request"), checkout)
    if mode == FREE:
        # G8: free joining activates at once whatever the timing, and the term carries no price.
        assert row.state == "active"
        assert (row.first_term_amount, row.joining_fee) == (0, 0)
        membership = MakerspaceMembership.objects.get(makerspace=makerspace, user=applicant)
        assert MembershipTerm.objects.get(membership=membership).plan_id == plan.pk
        return
    assert payment.amount == Decimal("25.00")
    assert row.state == ("awaiting_payment" if timing == "before_activation" else "active")


def _donor(space, name):
    from apps.payments.donations.identity import Donor
    from tests.return_helpers import make_member
    account = make_member(name, space)
    return Donor(account=account, name=name, email=f"{name}@example.test", actor=account)


@pytest.mark.parametrize("mode", MODES)
def test_a_gift_follows_the_donations_mode(mode, monkeypatch, django_capture_on_commit_callbacks):
    from apps.payments.donations.gates import DonationRefused
    from apps.payments.donations.services import checkout_url, create_gift
    from tests.return_helpers import make_space
    space = set_mode(make_space(f"mm-gift-{mode}"), "donations", mode)
    space.enabled_features = sorted(set(space.enabled_features) | {"finance.donations"})
    space.save(update_fields=["enabled_features"])
    checkout = fake_provider(monkeypatch) if mode == ONLINE else None
    donor = _donor(space, f"mm-gift-{mode}-donor")
    if mode == FREE:
        with pytest.raises(DonationRefused) as refused:
            create_gift(space, donor, amount=Decimal("50.00"))
        assert refused.value.detail["code"] == "charges_off"
        assert charges(space, "donation") == []
        return
    _gift, payment = create_gift(space, donor, amount=Decimal("50.00"))
    url = checkout_url(payment)
    assert bool(url) is (mode == ONLINE)
    assert_mode_outcome(mode, charges(space, "donation"), checkout)


@pytest.mark.parametrize("mode", MODES)
def test_sponsor_charges_and_pledges_follow_the_donations_mode(mode):
    from apps.payments.donations.gates import DonationRefused
    from apps.payments.donations.models import Sponsor
    from apps.payments.donations.pledges import create_pledge
    from apps.payments.donations.sponsors import raise_charge
    from tests.return_helpers import make_member, make_space
    space = set_mode(make_space(f"mm-sponsor-{mode}"), "donations", mode)
    staff = make_member(f"mm-sponsor-{mode}-sm", space)
    sponsor = Sponsor.objects.create(makerspace=space, name="Acme", created_by=staff)
    if mode == FREE:
        with pytest.raises(DonationRefused):
            raise_charge(sponsor, actor=staff, amount=Decimal("500.00"))
        with pytest.raises(DonationRefused):
            create_pledge(space, _donor(space, f"mm-pledge-{mode}"), amount=Decimal("10.00"), interval="monthly")
        assert charges(space, "sponsorship") == []
        return
    _charge, payment = raise_charge(sponsor, actor=staff, amount=Decimal("500.00"))
    assert payment.status == "pending" and charges(space, "sponsorship") == [payment]
