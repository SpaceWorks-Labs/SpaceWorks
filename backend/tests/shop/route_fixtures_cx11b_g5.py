"""Seed a real shop without an online rail or notification delivery adapters."""
from types import SimpleNamespace

from apps.makerspaces.capabilities import FEATURES
from apps.payments.models import MakerspacePaymentSettings
from apps.shop.models import ShopSettings
from tests.accounts.account_factories import make_staff
from tests.modules.switch_matrix_helpers import live_space
from tests.modules.switch_matrix_object_helpers import client_for
from tests.payments.route_support_cx11b_g5 import foreign_client, personal_client
from tests.shop.helpers import product


def seed(native):
    space = live_space("g5-shop", {"shop", "events", "membership", "member_accounts", "request_workflow"})
    space.enabled_features = sorted({key for key in FEATURES if key.startswith("shop.")} |
                                    {"charges.enabled", "charges.shop"})
    space.save(update_fields=["enabled_features"])
    actor = make_staff(space, username="g5-shop-manager")
    buyer = make_staff(space, username="g5-shop-buyer")
    from tests.accounts.account_factories import make_membership
    make_membership(buyer, space)
    policy = ShopSettings.objects.create(makerspace=space, policy_text="G5 retained policy")
    rail, _ = MakerspacePaymentSettings.objects.get_or_create(makerspace=space)
    rail.default_currency = "inr"
    rail.save()
    row, variant = product(space, actor, price="12.50", stock=8)
    return SimpleNamespace(space=space, actor=actor, buyer=buyer, product=row, variant=variant, policy=policy, rail=rail,
                           client=client_for(actor, space, native), buyer_client=personal_client(buyer, space, native),
                           foreign=foreign_client(native))
