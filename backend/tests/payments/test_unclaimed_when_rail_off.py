"""A NEW charge is stamped with a vendor only while the online rail is genuinely on (decision 470).

`payments` is opt-in and buys the rail alone. Saved credentials under an uninstalled module, a switched-off master
switch or a switched-off domain must not stamp a vendor: the debt is born `unclaimed`, and the first checkout that
reaches a provider claims it exactly once, after the rail is back on. A charge that already carries a stamp keeps it.
"""
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.makerspaces.models import MakerspaceMembership
from apps.makerspaces.module_install import install_module, uninstall_module
from apps.payments.models import Payment
from apps.payments.services import create_payment
from tests.payments.account_helpers import make_payer
from tests.payments.test_models import configured_settings
from tests.return_helpers import enable_online_rail, make_space

pytestmark = pytest.mark.django_db


def _raise(space, member, subject_id):
    return create_payment(makerspace=space, subject_type=Payment.SubjectType.MAKERSPACE_MEMBERSHIP,
                          subject_id=subject_id, member=member, amount=Decimal("20.00"), currency="usd",
                          created_by=member)


def _world(slug):
    space = make_space(slug)
    enable_online_rail(space, "membership")
    configured_settings(space)  # saved Stripe credentials
    member = make_payer(f"{slug}-m", space)
    return space, member, MakerspaceMembership.objects.get(makerspace=space, user=member)


def _switch_off(space, how):
    if how == "module":
        uninstall_module(space, "payments")
    elif how == "master":
        space.enabled_features = [k for k in space.enabled_features if k != "payments.enabled"]
        space.save(update_fields=["enabled_features"])
    else:
        space.enabled_features = [k for k in space.enabled_features if k != "payments.membership"]
        space.save(update_fields=["enabled_features"])
    space.refresh_from_db()


def test_with_every_clause_on_the_charge_is_stamped_with_the_vendor():
    space, member, membership = _world("ur-on")
    payment = _raise(space, member, membership.pk)
    assert payment.provider == Payment.Provider.STRIPE


@pytest.mark.parametrize("how", ["module", "master", "domain"])
def test_each_switched_off_clause_with_saved_credentials_raises_an_unclaimed_debt(how):
    space, member, membership = _world(f"ur-{how}")
    _switch_off(space, how)
    payment = _raise(space, member, membership.pk)
    assert (payment.provider, payment.status) == (Payment.Provider.UNCLAIMED, Payment.Status.PENDING)
    assert payment.online_rail is None


def test_re_enabling_the_rail_and_checking_out_claims_the_debt_exactly_once(monkeypatch):
    space, member, membership = _world("ur-reclaim")
    uninstall_module(space, "payments")
    payment = _raise(space, member, membership.pk)
    assert payment.provider == Payment.Provider.UNCLAIMED
    install_module(space, "payments")
    space.refresh_from_db()
    enable_online_rail(space, "membership")
    monkeypatch.setattr("apps.payments.services_checkout.member_payment_return_url", lambda _s: "https://x.example/m")
    calls = []

    def session(*_a, **_k):
        calls.append(1)
        return {"id": "cs_reclaim", "url": "https://checkout.stripe.test/cs_reclaim"}

    monkeypatch.setattr("apps.payments.services_checkout.stripe_client.create_checkout_session", session)
    client = APIClient()
    client.force_authenticate(member)
    url = f"/api/v1/member/makerspaces/{space.pk}/payments/{payment.pk}/checkout"
    assert client.post(url).status_code == 200
    payment.refresh_from_db()
    assert (payment.provider, payment.stripe_checkout_session_id) == (Payment.Provider.STRIPE, "cs_reclaim")
    client.post(url)  # a second attempt reuses the live session; the stamp never moves
    payment.refresh_from_db()
    assert payment.provider == Payment.Provider.STRIPE and len(calls) == 1


def test_a_charge_already_stamped_keeps_its_vendor_when_the_module_goes_off():
    space, member, membership = _world("ur-keep")
    payment = _raise(space, member, membership.pk)
    uninstall_module(space, "payments")
    assert Payment.objects.get(pk=payment.pk).provider == Payment.Provider.STRIPE
