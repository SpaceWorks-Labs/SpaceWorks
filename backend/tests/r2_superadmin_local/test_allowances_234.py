"""#234 addendum 3(a): remaining allowance per role, and the upload byte caps (addendum 2)."""

import pytest
from rest_framework.exceptions import ValidationError

from apps.makerspaces import limits
from apps.managed_hosting import hosting_type
from apps.managed_hosting.limits_role import allowance_rows
from tests.accounts.account_factories import make_staff

from .helpers import api, member, space, superadmin

pytestmark = pytest.mark.django_db
ADMIN = "/api/v1/admin/makerspace"


@pytest.fixture
def hosted_lab(settings):
    settings.PLATFORM_DOMAIN_SUFFIX = ""
    settings.MANAGED_PLANS_ENABLED = True
    lab = space("allowance-lab", resource_limit_overrides={
        "products": 10, "machines": 4, "members": 2, "api_clients": 1, "upload_bytes": 1024, "storage": 4096})
    hosting_type.set_type(superadmin(), lab, hosting_type.HOSTED)
    return lab


def test_space_manager_sees_every_limited_row_with_what_is_left(hosted_lab):
    boss = make_staff(hosted_lab, username="allowance-boss")
    body = api(boss).get(f"{ADMIN}/{hosted_lab.pk}/allowances").json()
    keys = {row["key"] for row in body["rows"]}
    assert {"products", "machines", "members", "api_clients", "storage", "upload_bytes"} <= keys
    products = next(row for row in body["rows"] if row["key"] == "products")
    assert products["limit"] == 10 and products["remaining"] == 10 - products["used"] and products["level"] == "ok"
    cap = next(row for row in body["rows"] if row["key"] == "upload_bytes")
    assert cap["used"] is None and cap["remaining"] is None  # a per-file cap counts nothing
    assert "events" not in keys  # unlimited rows are never listed


def test_an_area_manager_sees_only_their_area(hosted_lab):
    inventory = make_staff(hosted_lab, username="allowance-inv", role_slug="inventory_manager")
    body = api(inventory).get(f"{ADMIN}/{hosted_lab.pk}/allowances").json()
    keys = {row["key"] for row in body["rows"]}
    assert "inventory" in body["areas"] and {"products", "storage", "upload_bytes"} <= keys
    assert "api_clients" not in keys  # Space Manager-only rows never reach an area manager
    machines = make_staff(hosted_lab, username="allowance-mach", role_slug="machine_manager")
    machine_keys = {row["key"] for row in allowance_rows(machines, hosted_lab)["rows"]}
    assert "machines" in machine_keys and "api_clients" not in machine_keys
    narrowed = api(inventory).get(f"{ADMIN}/{hosted_lab.pk}/allowances?area=bookings").json()
    assert narrowed["rows"] == []  # asking for another area never widens what you manage
    assert api(inventory).get(f"{ADMIN}/{hosted_lab.pk}/allowances?area=nope").status_code == 400


def test_members_and_strangers_get_no_staff_allowances(hosted_lab):
    other = space("allowance-other")
    stranger = make_staff(other, username="allowance-stranger")
    assert api(stranger).get(f"{ADMIN}/{hosted_lab.pk}/allowances").status_code == 404
    assert api(member(hosted_lab)).get(f"{ADMIN}/{hosted_lab.pk}/allowances").status_code in (403, 404)


def test_warning_at_80_and_limit_at_100(hosted_lab):
    from apps.inventory.models import InventoryProduct

    for index in range(8):
        InventoryProduct.objects.create(makerspace=hosted_lab, name=f"Item {index}")
    boss = make_staff(hosted_lab, username="allowance-warn")
    row = next(r for r in allowance_rows(boss, hosted_lab)["rows"] if r["key"] == "products")
    assert row["percent"] == 80.0 and row["level"] == "warning"
    for index in range(2):
        InventoryProduct.objects.create(makerspace=hosted_lab, name=f"More {index}")
    row = next(r for r in allowance_rows(boss, hosted_lab)["rows"] if r["key"] == "products")
    assert row["level"] == "limit" and row["remaining"] == 0


def test_own_space_shows_only_limits_the_superadmin_set(settings, own_by_default):
    # Decision 281 addendum: a limit the superadmin SET applies to own spaces too (236 relaxed for
    # explicit limits only); with nothing set an own space has no limited rows.
    settings.MANAGED_PLANS_ENABLED = True
    plain = space("allowance-plain-own")
    boss = make_staff(plain, username="allowance-plain-boss")
    assert api(boss).get(f"{ADMIN}/{plain.pk}/allowances").json()["rows"] == []
    lab = space("allowance-own", resource_limit_overrides={"products": 1})
    boss = make_staff(lab, username="allowance-own-boss")
    rows = api(boss).get(f"{ADMIN}/{lab.pk}/allowances").json()["rows"]
    assert [row["key"] for row in rows] == ["products"] and rows[0]["limit"] == 1


def test_upload_caps_refuse_a_big_file_and_a_full_budget(hosted_lab, monkeypatch):
    limits.check_upload_size(hosted_lab, 1024)
    with pytest.raises(ValidationError) as caught:
        limits.check_upload_size(hosted_lab, 1025)
    assert caught.value.detail["code"] == "upload_limit"
    with pytest.raises(ValidationError):
        limits.check_upload_headroom(hosted_lab, 2048)  # declared over the per-file cap
    monkeypatch.setattr("apps.makerspaces.limits_usage._storage", lambda _space: 4096)
    with pytest.raises(ValidationError):
        limits.check_upload_headroom(hosted_lab)  # storage budget already spent
    charged = []
    monkeypatch.setattr("apps.makerspaces.limits.add_storage", lambda space_, size: charged.append(size))
    with pytest.raises(ValidationError):
        limits.charge_upload(hosted_lab, 5000)
    assert charged == []  # refused before anything is charged
    limits.charge_upload(hosted_lab, 100)
    assert charged == [100]


def test_upload_caps_are_dormant_without_hosting(settings):
    settings.PLATFORM_DOMAIN_SUFFIX = ""
    settings.MANAGED_PLANS_ENABLED = False
    # Decision 281 addendum: only a limit the superadmin SET applies; with none set nothing is checked.
    lab = space("allowance-plain")
    limits.check_upload_headroom(lab, 10_000_000)
    limits.check_upload_size(lab, 10_000_000)
    capped = space("allowance-capped", resource_limit_overrides={"upload_bytes": 1})
    with pytest.raises(ValidationError):
        limits.check_upload_size(capped, 10_000_000)


def test_member_sees_their_own_allowances(hosted_lab):
    from apps.makerspaces.models_loan_policy import MakerspaceLoanPolicy

    hosted_lab.enabled_features = sorted(set(hosted_lab.enabled_features or []) | {"loans.limits"})
    hosted_lab.save(update_fields=["enabled_features"])
    MakerspaceLoanPolicy.objects.update_or_create(makerspace=hosted_lab, defaults={
        "loan_max_active": 3, "loan_max_items": 5, "default_loan_days": 7})
    person = member(hosted_lab, "allowance-member")
    response = api(person).get(f"/api/v1/member/makerspaces/{hosted_lab.pk}/allowances")
    assert response.status_code == 200
    body = response.json()
    assert body["borrowing"]["active_loans"] == {"used": 0, "limit": 3, "remaining": 3, "percent": 0.0, "level": "ok"}
    assert body["borrowing"]["items_out"]["limit"] == 5
    assert set(body) == {"makerspace_id", "borrowing", "included_hours", "guest_passes", "day_passes"}


def test_member_allowances_need_an_active_membership(hosted_lab):
    outsider = member(space("allowance-elsewhere"), "allowance-outsider")
    assert api(outsider).get(f"/api/v1/member/makerspaces/{hosted_lab.pk}/allowances").status_code in (403, 404)


def test_renewals_left_counts_down_from_the_policy_cap():
    from types import SimpleNamespace

    from apps.hardware_requests.models import HardwareRequest
    from apps.hardware_requests.renewal_state import RenewalStateResolver
    from apps.makerspaces.models_loan_policy import MakerspaceLoanPolicy

    resolver = RenewalStateResolver.__new__(RenewalStateResolver)
    resolver.enabled = True
    resolver.policy = SimpleNamespace(loan_renewal_mode=MakerspaceLoanPolicy.RenewalMode.AUTO, loan_max_renewals=3)
    product = SimpleNamespace(max_renewals=None, category_id=None)
    item = SimpleNamespace(product=product, issued_quantity=1, returned_quantity=0, damaged_quantity=0, missing_quantity=0)
    loan = SimpleNamespace(status=HardwareRequest.Status.ISSUED, renewal_count=1,
                           items=SimpleNamespace(all=lambda: [item]))
    assert resolver.renewals_left(loan) == 2
    loan.renewal_count = 5
    assert resolver.renewals_left(loan) == 0
    resolver.enabled = False
    assert resolver.renewals_left(loan) is None
