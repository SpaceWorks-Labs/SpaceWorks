"""Shared fixtures for the lane L22 shop tests (local, untracked)."""

from decimal import Decimal

from apps.makerspaces.models import Makerspace
from tests.payments.account_helpers import make_payer
from tests.return_helpers import authenticated_client, make_member, make_space

BASE = ("charges.enabled", "charges.shop", "billing.documents")


def switch(space, *keys, on=True, modules=()):
    features = set(space.enabled_features or [])
    features = features | set(keys) if on else features - set(keys)
    mods = set(space.enabled_modules or []) | set(modules)
    Makerspace.objects.filter(pk=space.pk).update(enabled_features=sorted(features), enabled_modules=sorted(mods))
    space.refresh_from_db()
    return space


def module_off(space):
    Makerspace.objects.filter(pk=space.pk).update(
        enabled_modules=sorted(set(space.enabled_modules or []) - {"shop"}))
    space.refresh_from_db()
    return space


def shop_space(slug, *features):
    space = make_space(slug)
    Makerspace.objects.filter(pk=space.pk).update(public_site_enabled=True)
    return switch(space, *BASE, *features, modules=("shop",))


def manager(space, slug=None):
    return make_member(f"{slug or space.slug}-sm", space)


def shop_manager(space, slug=None):
    return make_member(f"{slug or space.slug}-shopm", space, membership_role="shop_manager")


def staff(space, role, slug=None):
    return make_member(f"{slug or space.slug}-{role}", space, membership_role=role)


def member(space, name="buyer"):
    return make_payer(f"{space.slug}-{name}", space)


def client(user=None):
    from rest_framework.test import APIClient
    return authenticated_client(user) if user is not None else APIClient()


def product(space, actor, *, name="Widget", price="100.00", stock=10, kind="other", **extra):
    from apps.shop.services_catalogue import move_stock, save_product

    data = {"kind": kind, "name": name, "variants": [{"name": "Standard", "price": Decimal(price),
                                                       "sku": extra.pop("sku", "")}], **extra}
    row = save_product(space, data, actor=actor)
    variant = row.variants.get()
    if stock:
        move_stock(variant, actor=actor, kind="restock", quantity=stock, reason="seed")
    variant.refresh_from_db()
    return row, variant


def line(variant, quantity=1):
    return {"variant_id": variant.pk, "quantity": quantity}


def payment_for(order):
    from apps.shop.orders_core import order_payment
    return order_payment(order)
