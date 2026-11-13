"""MOD-1B: the public notify-me watch route (POST subscribe / DELETE unsubscribe), condition by condition.

Complements tests/test_inventory_notify_me.py (once-per-rise dispatch, hidden counts, one 400/404 sweep) with exact
codes, idempotency (a double click or a repeated delete leaves one row and one audit entry per real change),
tenancy, the module and capability switches, and who may subscribe.
"""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.inventory.models import InventoryProduct
from apps.inventory.models_watch import InventoryWatch
from tests.return_helpers import make_member, make_space

pytestmark = pytest.mark.django_db


def world(slug, **product):
    space = make_space(slug)
    space.enabled_features = sorted(set(space.enabled_features) | {"inventory.notify_when_back"})
    space.public_inventory_enabled = True
    space.save(update_fields=["enabled_features", "public_inventory_enabled"])
    member = make_member(slug + "-member", space, "member", role=User.Role.REQUESTER)
    defaults = dict(makerspace=space, name="Drill", total_quantity=1, available_quantity=0, issued_quantity=1)
    defaults.update(product)
    return space, member, InventoryProduct.objects.create(**defaults)


def url(space, product):
    return reverse("public-inventory-watch", kwargs={"makerspace_slug": space.slug, "pk": product.pk})


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def actions(name):
    return AuditLog.objects.filter(action=name).count()


def test_subscribe_and_unsubscribe_each_write_one_row_change_and_one_audit_entry():
    space, member, product = world("mod1b-watch-ok")
    client = client_for(member)
    reply = client.post(url(space, product), {}, format="json")
    assert reply.status_code == 200 and reply.data == {"subscribed": True}
    assert InventoryWatch.objects.filter(product=product, user=member).count() == 1
    assert actions("inventory.watch_subscribed") == 1
    gone = client.delete(url(space, product))
    assert gone.status_code == 204
    assert not InventoryWatch.objects.filter(product=product, user=member).exists()
    assert actions("inventory.watch_unsubscribed") == 1


def test_a_double_click_subscribe_keeps_one_row_and_one_audit_entry():
    space, member, product = world("mod1b-watch-twice")
    client = client_for(member)
    assert client.post(url(space, product), {}, format="json").status_code == 200
    assert client.post(url(space, product), {}, format="json").status_code == 200
    assert InventoryWatch.objects.filter(product=product, user=member).count() == 1
    assert actions("inventory.watch_subscribed") == 1


def test_a_repeated_delete_is_a_204_and_audits_only_the_real_removal():
    space, member, product = world("mod1b-watch-del2")
    client = client_for(member)
    client.post(url(space, product), {}, format="json")
    assert client.delete(url(space, product)).status_code == 204
    assert client.delete(url(space, product)).status_code == 204
    assert actions("inventory.watch_unsubscribed") == 1


def test_an_item_already_in_stock_cannot_be_watched():
    space, member, product = world("mod1b-watch-instock", total_quantity=3, available_quantity=3, issued_quantity=0)
    reply = client_for(member).post(url(space, product), {}, format="json")
    assert reply.status_code == 400 and "already available" in str(reply.data)
    assert not InventoryWatch.objects.exists()


@pytest.mark.parametrize("flags", [{"is_public": False}, {"is_archived": True}])
def test_a_private_or_archived_item_is_a_404_for_subscribe_and_unsubscribe(flags):
    space, member, product = world("mod1b-watch-hidden-" + next(iter(flags)), **flags)
    client = client_for(member)
    assert client.post(url(space, product), {}, format="json").status_code == 404
    assert client.delete(url(space, product)).status_code == 404
    assert not InventoryWatch.objects.exists()


def test_hidden_availability_mode_refuses_the_watch_without_leaking_a_count():
    space, member, product = world("mod1b-watch-hiddenmode", public_availability_mode="hidden")
    reply = client_for(member).post(url(space, product), {}, format="json")
    assert reply.status_code == 400 and "not public" in str(reply.data)
    assert not InventoryWatch.objects.exists()


def test_the_item_of_another_makerspace_is_a_404_under_this_slug():
    space, member, _product = world("mod1b-watch-tenant")
    _other, _m, foreign = world("mod1b-watch-tenant-2")
    assert client_for(member).post(url(space, foreign), {}, format="json").status_code == 404
    assert not InventoryWatch.objects.exists()


def test_signed_out_callers_are_refused_and_nothing_is_written():
    space, _member, product = world("mod1b-watch-anon")
    anonymous = APIClient()
    assert anonymous.post(url(space, product), {}, format="json").status_code in (401, 403)
    assert anonymous.delete(url(space, product)).status_code in (401, 403)
    assert not InventoryWatch.objects.exists()


def test_an_account_without_an_active_membership_cannot_subscribe():
    space, _member, product = world("mod1b-watch-nomember")
    stranger = make_member("mod1b-watch-stranger", make_space("mod1b-watch-elsewhere"), "member", role=User.Role.REQUESTER)
    reply = client_for(stranger).post(url(space, product), {}, format="json")
    assert reply.status_code in (403, 404), reply.data
    assert not InventoryWatch.objects.exists()


def test_the_capability_and_the_public_catalogue_switch_refuse_with_typed_codes_and_restore():
    space, member, product = world("mod1b-watch-switch")
    client = client_for(member)
    space.enabled_features = [key for key in space.enabled_features if key != "inventory.notify_when_back"]
    space.save(update_fields=["enabled_features"])
    off = client.post(url(space, product), {}, format="json")
    assert off.status_code == 404 and off.data["code"] == "feature_disabled" and off.data["feature"] == "inventory.notify_when_back"
    space.enabled_features = sorted({*space.enabled_features, "inventory.notify_when_back"})
    space.save(update_fields=["enabled_features"])
    assert client.post(url(space, product), {}, format="json").status_code == 200
    # `public_inventory` is a core module (no off switch); the space-level public catalogue switch is the gate.
    space.public_inventory_enabled = False
    space.save(update_fields=["public_inventory_enabled"])
    gone = client.post(url(space, product), {}, format="json")
    assert gone.status_code == 400 and "Public inventory is disabled" in str(gone.data)
    assert InventoryWatch.objects.filter(product=product, user=member).count() == 1  # data kept


def test_the_request_body_may_not_carry_a_destination():
    space, member, product = world("mod1b-watch-body")
    reply = client_for(member).post(url(space, product), {"email": "x@example.com", "phone": "+15550000000"}, format="json")
    assert reply.status_code == 400
    assert not InventoryWatch.objects.exists()
