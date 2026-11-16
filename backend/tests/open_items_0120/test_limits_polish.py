"""Owner rule 261: storage limits on own spaces (accounting + backfill), plan rows and snapshots carry every key.

Written, not run, by the limits-polish lane.
"""
from unittest import mock

import pytest
from rest_framework.exceptions import ValidationError

from apps.makerspaces import limits
from apps.makerspaces.limits_storage_backfill import STORAGE_LIMIT_KEYS, backfill_if_newly_limited
from apps.makerspaces.limits_uploads import STORAGE_CLASS_KEYS, charge_upload, check_upload_headroom
from apps.makerspaces.models import Makerspace
from apps.makerspaces.usage_snapshot import usage_snapshot
from apps.managed_hosting import extra_quota_counters as counters
from apps.managed_hosting import extra_quotas as eq
from apps.managed_hosting import plans
from apps.managed_hosting.limit_catalogue import effective_limit, registry_keys
from apps.managed_hosting.models import HostingPlan
from apps.managed_hosting.usage import plan_usage
from tests.r2_superadmin_local.conftest import managed  # noqa: F401  (fixture, moved out of the root conftest)
from tests.r2_superadmin_local.helpers import api, space as make_hosted_space, superadmin
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db
PLATFORM = "/api/v1/admin/platform"


@pytest.fixture
def switch_off(settings):
    settings.PLATFORM_DOMAIN_SUFFIX = ""
    settings.MANAGED_PLANS_ENABLED = False


def _used(space):
    return Makerspace.objects.values_list("storage_bytes_used", flat=True).get(pk=space.pk)


def _limit(space, **values):
    space.resource_limit_overrides = {**(space.resource_limit_overrides or {}), **values}
    space.save(update_fields=["resource_limit_overrides"])


# --- 1. storage accounting runs on own spaces ----------------------------------------------------

def test_own_space_counts_bytes_even_with_no_limit(switch_off):
    lab = make_space("polish-count")
    limits.add_storage(lab, 300)
    assert _used(lab) == 300  # no self-host no-op any more
    limits.free_storage(lab, 100)
    assert _used(lab) == 200
    limits.free_storage(lab, 10 ** 6)
    assert _used(lab) == 0  # never below zero


def test_own_space_storage_limit_is_enforced_after_backfill(switch_off):
    lab = make_space("polish-own-limit")
    old = dict(lab.resource_limit_overrides or {})

    def recompute(name, selector, **kwargs):
        Makerspace.objects.filter(pk=int(selector)).update(storage_bytes_used=900)  # the real usage

    with mock.patch("apps.makerspaces.limits_storage_backfill.call_command", side_effect=recompute) as ran:
        assert backfill_if_newly_limited(lab, old, {"storage": 1000}) is True
        ran.assert_called_once()
    _limit(lab, storage=1000)
    limits.add_storage(lab, 100)  # 900 + 100 fits exactly
    with pytest.raises(ValidationError) as refused:
        limits.add_storage(lab, 1)
    assert "limit" in refused.value.detail
    lab.refresh_from_db()  # add_storage charges with an F() update; a request re-reads the row, the test must too
    with pytest.raises(ValidationError):
        check_upload_headroom(lab, 1)  # presign is refused too: no self-host early return


def test_backfill_runs_only_for_the_first_storage_limit(switch_off):
    lab = make_space("polish-backfill-once")
    with mock.patch("apps.makerspaces.limits_storage_backfill.call_command") as ran:
        assert backfill_if_newly_limited(lab, {}, {"products": 5}) is False  # not a storage key
        assert backfill_if_newly_limited(lab, {}, {"storage": None}) is False  # nothing set
        assert backfill_if_newly_limited(lab, {"storage": 10}, {"storage": 20}) is False  # already limited
        assert backfill_if_newly_limited(lab, {}, {"storage_evidence_bytes": 5}) is True
        assert ran.call_count == 1
    assert set(STORAGE_LIMIT_KEYS) == {"storage", "storage_evidence_bytes", "storage_public_images_bytes"}


def test_setting_the_first_storage_limit_through_the_console_backfills(switch_off):
    lab = make_space("polish-console")
    root = superadmin("polish-root")
    with mock.patch("apps.makerspaces.limits_storage_backfill.call_command") as ran:
        response = api(root).put(f"{PLATFORM}/spaces/{lab.pk}/limits", {"overrides": {"storage": 5000}}, format="json")
    assert response.status_code == 200
    ran.assert_called_once()


def test_evidence_and_public_image_limits_are_separate_classes(switch_off):
    lab = make_space("polish-split")
    Makerspace.objects.filter(pk=lab.pk).update(storage_bytes_used=150)
    _limit(lab, storage_evidence_bytes=100, storage_public_images_bytes=50)
    lab.refresh_from_db()
    assert STORAGE_CLASS_KEYS == {"evidence": "storage_evidence_bytes", "public_image": "storage_public_images_bytes"}
    with mock.patch.object(counters, "storage_evidence_bytes", return_value=100), \
            mock.patch.dict(counters.COUNTERS, {"storage_evidence_bytes": lambda space: 100}):
        assert counters.storage_public_images_bytes(lab) == 50  # total minus evidence
        with pytest.raises(eq.ExtraQuotaReached) as evidence:
            charge_upload(lab, 1, kind="evidence")
        assert evidence.value.code == "storage_evidence_bytes_quota_reached"
        with pytest.raises(eq.ExtraQuotaReached) as image:
            charge_upload(lab, 1, kind="public_image")
        assert image.value.code == "storage_public_images_bytes_quota_reached"
    assert _used(lab) == 150  # refused uploads charged nothing


def test_release_on_delete_frees_room(switch_off):
    lab = make_space("polish-release")
    _limit(lab, storage=100)
    limits.add_storage(lab, 100)
    with pytest.raises(ValidationError):
        limits.add_storage(lab, 1)
    limits.free_storage(lab, 60)  # a deletion, or an evidence object expiring under retention
    limits.add_storage(lab, 60)
    assert _used(lab) == 100


# --- 2. plans and snapshots carry every registry key ---------------------------------------------

def test_plan_accepts_every_registry_key_and_rejects_unknown():
    for key in registry_keys():
        assert plans.validate_limits({key: 3}) == {key: 3}
    with pytest.raises(ValidationError):
        plans.validate_limits({"nonsense_key": 1})


def test_plan_with_new_keys_applies_to_a_hosted_space(managed):
    lab = make_hosted_space("polish-plan")
    root = superadmin("polish-plan-root")
    plan = HostingPlan.objects.create(key="polish", name="Polish", trial_days=0, limits={
        "shop_products": 7, "storage_evidence_bytes": 4096, "platform_email_monthly": 12, "events_monthly": 3})
    managed.MANAGED_PLANS_ENABLED = True
    plans.assign(root, lab.pk, plan.pk, trial_days=0)
    assert effective_limit(lab, "shop_products") == 7
    assert effective_limit(lab, "storage_evidence_bytes") == 4096
    assert effective_limit(lab, "platform_email_monthly") == 12
    with pytest.raises(eq.ExtraQuotaReached):
        eq.check_extra_quota(lab, "storage_evidence_bytes", adding=5000)
    rows = {row["key"]: row for row in plan_usage(lab)["resources"]}
    assert {"shop_products", "storage_evidence_bytes", "platform_email_monthly", "events_monthly"} <= set(rows)
    assert rows["storage_evidence_bytes"]["unit"] == "bytes" and rows["storage_evidence_bytes"]["area"] == "storage"
    _limit(lab, shop_products=2)  # an override beats the plan
    assert effective_limit(lab, "shop_products") == 2


def test_usage_snapshot_lists_every_registry_key_grouped_by_area(switch_off):
    lab = make_space("polish-snapshot")
    _limit(lab, shop_products=4, storage_public_images_bytes=1000)
    resources = usage_snapshot(lab)["resources"]
    assert [row["key"] for row in resources] == registry_keys()
    by_key = {row["key"]: row for row in resources}
    assert by_key["shop_products"]["limit"] == 4 and by_key["shop_products"]["used"] == 0
    assert by_key["storage_public_images_bytes"]["unit"] == "bytes"
    assert by_key["devices"]["limit"] is None and by_key["devices"]["used"] is None  # unlimited: not counted
    assert {row["area"] for row in resources} >= {"shop", "storage", "money", "messaging"}
