"""Saved vendors and machine-type options: exact scoped rows and switch restoration."""
import pytest

from apps.procurement.models import Vendor
from tests.machines.route_support_cx11b_g2 import command, prove, world

pytestmark = [pytest.mark.django_db, pytest.mark.area_inventory, pytest.mark.area_machines]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("name,method", [("procurement-vendors", "get"), ("procurement-vendors", "post"),
                                       ("procurement-vendor-detail", "patch")])
def test_vendor_routes_persist_exact_changes_and_hide_from_outsider(native, name, method):
    w = world(native)
    vendor = Vendor.objects.create(makerspace=w.space, name="Retained supplier", created_by=w.actor)
    args = [w.space.pk, vendor.pk] if method == "patch" else [w.space.pk]

    def check(response):
        if method == "get":
            assert [(r["id"], r["name"]) for r in response.data] == [(vendor.pk, "Retained supplier")]
        else:
            saved = Vendor.objects.get(pk=response.data["id"])
            assert (saved.makerspace_id, saved.name, saved.email) == (
                w.space.pk, "Updated supplier", "supplier@example.test")
            assert Vendor.objects.filter(makerspace=w.space).count() == (2 if method == "post" else 1)

    # Makerspace-id staff routes: 481/494, independent from successful empty To-Buy list.
    prove(w, "inventory.vendors", lambda c: command(c, f"procurement:{name}", method, args,
          {"name": "Updated supplier", "email": "supplier@example.test"}), check,
          status=201 if method == "post" else 200, off=(404, "capability_disabled"),
          audits={"post": ("vendor.created",), "patch": ("vendor.updated",)}.get(method, ()))


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["inventory.tobuy", "machines.tobuy", "machines"])
def test_type_options_any_parent_contract_retains_the_named_type(native, key):
    w = world(native)
    # This route depends on ANY live To-Buy stream. Removing one must keep it
    # available through the other stream; it is not owned by either individual row.
    def check(response):
        assert response.data["machine_type_required"] is False
        assert [(r["id"], r["name"]) for r in response.data["results"] if r["id"] == w.machine_type.pk] == [
            (w.machine_type.pk, w.machine_type.name)]

    prove(w, key, lambda c: command(c, "procurement:to-buy-machine-type-options", "get", [w.space.pk]),
          check, off=(200, None), off_check=check)
