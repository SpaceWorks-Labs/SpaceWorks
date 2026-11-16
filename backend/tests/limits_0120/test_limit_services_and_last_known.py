"""Limit writes go through one service, and a failed platform-default lookup keeps the last known value.

* Decision 335(b): a cache or database failure during a lookup never turns a configured default into
  "unlimited"; the last map read successfully applies.
* Codex arch-1 #10: single-space, bulk and platform-default writes share `managed_hosting.limit_services`.
* SECURITY-REVIEW L-M6: a default larger than the bigint column is a 400, not a 500; messages are translated.
"""
import pytest
from django.core.cache import cache

from apps.audit.models import AuditLog
from apps.managed_hosting import limit_defaults, limit_services
from apps.managed_hosting.models import PlatformLimitDefault
from tests.r2_superadmin_local.helpers import api, superadmin
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db
URL = "/api/v1/admin/platform/limit-defaults"


@pytest.fixture(autouse=True)
def _fresh(settings, monkeypatch):
    settings.PLATFORM_DOMAIN_SUFFIX = ""
    settings.MANAGED_PLANS_ENABLED = False
    cache.clear()
    monkeypatch.setattr(limit_defaults, "_last_known", None)
    yield
    cache.clear()


def _broken_database(monkeypatch):
    def boom(*_args, **_kwargs):
        raise RuntimeError("database unavailable")
    monkeypatch.setattr(PlatformLimitDefault.objects, "values_list", boom)


# --- last known value (decision 335(b)) -------------------------------------------------------------

def test_a_failed_lookup_keeps_the_last_known_default_not_unlimited(monkeypatch):
    PlatformLimitDefault.objects.create(key="products", value=5)
    assert limit_defaults.platform_default("products") == 5
    cache.delete(limit_defaults.CACHE_KEY)  # the short cache expired ...
    _broken_database(monkeypatch)            # ... and the database is down
    assert limit_defaults.platform_default("products") == 5
    assert limit_defaults.any_default() is True


def test_a_new_process_uses_the_shared_last_known_copy(monkeypatch):
    PlatformLimitDefault.objects.create(key="boxes", value=3)
    limit_defaults.all_defaults()
    cache.delete(limit_defaults.CACHE_KEY)
    monkeypatch.setattr(limit_defaults, "_last_known", None)  # a fresh worker
    _broken_database(monkeypatch)
    assert limit_defaults.platform_default("boxes") == 3


def test_a_cache_outage_still_reads_the_database(monkeypatch):
    PlatformLimitDefault.objects.create(key="products", value=7)

    def down(*_args, **_kwargs):
        raise ConnectionError("cache down")
    monkeypatch.setattr(limit_defaults.cache, "get", down)
    monkeypatch.setattr(limit_defaults.cache, "set", down)
    monkeypatch.setattr(limit_defaults.cache, "delete", down)
    assert limit_defaults.platform_default("products") == 7
    limit_defaults.invalidate()  # never raises


def test_with_nothing_ever_read_and_everything_down_there_is_no_default(monkeypatch):
    _broken_database(monkeypatch)
    assert limit_defaults.platform_default("products") is None


def test_a_write_is_seen_by_the_next_read():
    root = superadmin("lk-root")
    limit_services.set_platform_defaults(root, {"products": 4})
    assert limit_defaults.platform_default("products") == 4
    limit_services.set_platform_defaults(root, {"products": None})
    assert limit_defaults.platform_default("products") is None


# --- shared services --------------------------------------------------------------------------------

def test_replace_and_bulk_write_the_same_audit_row():
    root = superadmin("lk-root2")
    a, b = make_space("lk-a"), make_space("lk-b")
    limit_services.replace_space_overrides(root, a.pk, {"products": 3})
    limit_services.bulk_update_space_overrides(root, [a.pk, b.pk], {"boxes": 2}, ["products"],
                                               on_unknown=lambda pk: AssertionError(pk))
    a.refresh_from_db()
    b.refresh_from_db()
    assert a.resource_limit_overrides == {"boxes": 2} and b.resource_limit_overrides == {"boxes": 2}
    rows = AuditLog.objects.filter(action="space_control.limits_changed", makerspace=a).order_by("pk")
    assert [row.meta["changed"] for row in rows] == [["products"], ["boxes", "products"]]


def test_bulk_is_all_or_nothing_on_an_unknown_space():
    root = superadmin("lk-root3")
    a = make_space("lk-c")

    class Unknown(Exception):
        pass
    with pytest.raises(Unknown):
        limit_services.bulk_update_space_overrides(root, [a.pk, 999999], {"boxes": 1}, [],
                                                   on_unknown=lambda pk: Unknown(pk))
    a.refresh_from_db()
    assert not (a.resource_limit_overrides or {}).get("boxes")
    assert not AuditLog.objects.filter(action="space_control.limits_changed").exists()


def test_bulk_endpoint_still_answers_409_for_an_unknown_space():
    a = make_space("lk-d")
    response = api(superadmin("lk-root4")).post("/api/v1/admin/platform/spaces/limits-bulk",
                                                {"makerspace_ids": [a.pk, 999999], "set": {"boxes": 1}},
                                                format="json")
    assert response.status_code == 409 and response.json()["failed_id"] == 999999
    a.refresh_from_db()
    assert not (a.resource_limit_overrides or {}).get("boxes")


# --- validation (L-M6, translated messages) ---------------------------------------------------------

@pytest.mark.parametrize("value", [2**63, 10**30])
def test_an_oversized_default_is_a_400_not_a_500(value):
    response = api(superadmin("lk-root5")).put(URL, {"defaults": {"products": value}}, format="json")
    assert response.status_code == 400 and not PlatformLimitDefault.objects.exists()


def test_the_largest_bigint_is_accepted():
    response = api(superadmin("lk-root6")).put(URL, {"defaults": {"products": 2**63 - 1}}, format="json")
    assert response.status_code == 200
    assert PlatformLimitDefault.objects.get(key="products").value == 2**63 - 1


def test_validation_messages_are_translatable():
    from django.utils import translation
    from apps.managed_hosting import views_limit_defaults
    with translation.override("en"):
        with pytest.raises(Exception) as raised:
            views_limit_defaults._clean({"nope": 1})
    assert "Unknown limit key." in str(raised.value.detail)
