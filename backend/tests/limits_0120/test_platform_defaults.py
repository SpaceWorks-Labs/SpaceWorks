"""Decision 328a: platform default limits. Order: space override, hosted plan, platform default, unlimited."""
import pytest
from django.core.cache import cache

from apps.audit.models import AuditLog
from apps.makerspaces.limits_core import resource_limit
from apps.managed_hosting import extra_quotas as eq
from apps.managed_hosting import platform_limits as pl
from apps.managed_hosting import space_quotas as sq
from apps.managed_hosting.limit_defaults import all_defaults, any_default, platform_default
from apps.managed_hosting.models import PlatformLimitDefault
from tests.accounts.account_factories import make_staff
from tests.open_items_0120.test_platform_credential_limits import _limit
from tests.r2_superadmin_local.helpers import api, manager, member, space as hosted_space, superadmin
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db
URL = "/api/v1/admin/platform/limit-defaults"


@pytest.fixture(autouse=True)
def _fresh_cache(settings):
    settings.PLATFORM_DOMAIN_SUFFIX = ""
    settings.MANAGED_PLANS_ENABLED = False
    cache.clear()
    yield
    cache.clear()


def _default(key, value):
    PlatformLimitDefault.objects.update_or_create(key=key, defaults={"value": value})


def test_nothing_is_limited_by_default():
    space = make_space("pd-fresh")
    assert not any_default() and all_defaults() == {}
    assert resource_limit(space, "products") is None
    assert sq.quota_limit(space, "shop_products") is None
    assert pl.platform_limit(space, "platform_sms_monthly") is None


def test_a_default_applies_to_every_resolver_family():
    space = make_space("pd-families")
    _default("products", 5)
    _default("shop_products", 7)
    _default("platform_sms_monthly", 9)
    _default("events_monthly", 3)
    assert resource_limit(space, "products") == 5
    assert sq.quota_limit(space, "shop_products") == 7 and sq.quota_limit(space, "events_monthly") == 3
    assert pl.platform_limit(space, "platform_sms_monthly") == 9
    assert platform_default("members") is None


def test_the_space_override_wins_including_no_limit():
    space = make_space("pd-override")
    _default("products", 5)
    _default("shop_products", 7)
    _limit(space, products=50, shop_products=-1)
    assert resource_limit(space, "products") == 50
    assert sq.quota_limit(space, "shop_products") is None  # -1 on the space beats a default of 7


def test_a_hosted_plan_wins_over_the_default(monkeypatch):
    from apps.managed_hosting import enforcement
    space = make_space("pd-plan")
    _default("products", 5)
    monkeypatch.setattr("apps.makerspaces.limits.is_self_host", lambda: False)
    monkeypatch.setattr("apps.managed_hosting.hosting_type.is_hosted", lambda _space: True)
    monkeypatch.setattr(enforcement, "plan_limit", lambda _space, key: 11 if key == "products" else enforcement.NOT_SET)
    assert resource_limit(space, "products") == 11
    monkeypatch.setattr(enforcement, "plan_limit", lambda _space, key: enforcement.NOT_SET)
    assert resource_limit(space, "products") == 5


def test_a_default_refuses_only_the_start_of_something_new_with_the_typed_409():
    from apps.boxes.models import Box
    space = make_space("pd-refuse")
    for label in ("A", "B"):
        Box.objects.create(makerspace=space, label=label)
    _default("boxes", 2)
    with pytest.raises(eq.ExtraQuotaReached) as raised:
        eq.check_extra_quota(space, "boxes")
    assert raised.value.status_code == 409 and raised.value.code == "boxes_quota_reached"
    assert "reached its allowance" in str(raised.value.detail["detail"]) and "platform operator" in str(raised.value.detail["detail"])
    assert Box.objects.filter(makerspace=space).count() == 2  # existing data untouched


def test_payment_capacity_runs_when_only_a_default_exists():
    space = make_space("pd-pay")
    _default("payments_monthly_count", 0)
    with pytest.raises(sq.SpaceQuotaReached):
        sq.require_payment_capacity(space, 10, "usd")


# --- API: superadmin only, audited, validated ---------------------------------------------------

def test_superadmin_reads_every_key_grouped_by_module_with_default_null():
    body = api(superadmin("pd-root")).get(URL).json()
    assert body["groups"] and all(row["default"] is None for row in body["rows"])
    keys = {row["key"] for row in body["rows"]}
    assert {"products", "adapter_media_bytes", "anthias_players", "custom_domain"} & keys == {"products", "adapter_media_bytes", "anthias_players"}
    assert all(row["group"] and row["module"] for row in body["rows"])


def test_put_sets_clears_and_audits_the_change():
    root = superadmin("pd-root2")
    client = api(root)
    response = client.put(URL, {"defaults": {"products": 9, "boxes": 4}}, format="json")
    assert response.status_code == 200
    assert {r["key"]: r["default"] for r in response.json()["rows"] if r["default"] is not None} == {"products": 9, "boxes": 4}
    assert resource_limit(make_space("pd-after"), "products") == 9  # the cache was cleared on write
    entry = AuditLog.objects.get(action="managed_hosting.limit_defaults_changed")
    assert entry.meta["changed"] == ["boxes", "products"] and entry.meta["to"] == {"boxes": 4, "products": 9}
    client.put(URL, {"defaults": {"products": None, "boxes": -1}}, format="json")
    assert not PlatformLimitDefault.objects.exists()
    cleared = AuditLog.objects.filter(action="managed_hosting.limit_defaults_changed").order_by("-pk").first()
    assert cleared.meta["from"] == {"boxes": 4, "products": 9} and cleared.meta["to"] == {"boxes": None, "products": None}


def test_an_unchanged_put_writes_no_audit_row():
    client = api(superadmin("pd-root3"))
    client.put(URL, {"defaults": {"products": 9}}, format="json")
    client.put(URL, {"defaults": {"products": 9}}, format="json")
    assert AuditLog.objects.filter(action="managed_hosting.limit_defaults_changed").count() == 1


@pytest.mark.parametrize("body", [{"nope": 1}, {"products": -2}, {"products": True}, {"products": "5"}, {"custom_domain": 1}])
def test_put_refuses_unknown_boolean_or_malformed_values(body):
    response = api(superadmin("pd-root4")).put(URL, {"defaults": body}, format="json")
    assert response.status_code == 400 and not PlatformLimitDefault.objects.exists()


def test_only_a_superadmin_may_read_or_write_defaults():
    lab = hosted_space("pd-lab")
    boss = manager(lab)
    for user in (boss, member(lab)):
        client = api(user)
        assert client.get(URL).status_code in (401, 403)
        assert client.put(URL, {"defaults": {"products": 1}}, format="json").status_code in (401, 403)
    assert api().get(URL).status_code in (401, 403)
    assert not PlatformLimitDefault.objects.exists()


# --- Space Manager: read-only limits and usage for their own space ------------------------------

def test_space_manager_reads_own_limits_grouped_by_module_with_the_source():
    lab = hosted_space("pd-view")
    boss = manager(lab)
    _default("products", 10)
    _limit(lab, boxes=0)
    body = api(boss).get(f"/api/v1/admin/makerspace/{lab.pk}/limits").json()
    rows = {row["key"]: row for row in body["rows"]}
    assert set(rows) == {"products", "boxes"}
    assert rows["products"]["source"] == "default" and rows["products"]["limit"] == 10 and rows["products"]["group"] == "inventory"
    assert rows["boxes"]["source"] == "override" and rows["boxes"]["level"] == "limit"
    assert body["groups"] and body["makerspace_id"] == lab.pk


def test_space_manager_view_is_scoped_and_read_only():
    lab, other = hosted_space("pd-scope-a"), hosted_space("pd-scope-b")
    boss = manager(lab)
    client = api(boss)
    assert client.get(f"/api/v1/admin/makerspace/{other.pk}/limits").status_code == 403
    assert client.post(f"/api/v1/admin/makerspace/{lab.pk}/limits", {}, format="json").status_code in (403, 405)
    assert api(member(lab)).get(f"/api/v1/admin/makerspace/{lab.pk}/limits").status_code == 403
    assert api(superadmin("pd-root5")).get(f"/api/v1/admin/makerspace/{lab.pk}/limits").status_code == 200
    assert make_staff is not None
