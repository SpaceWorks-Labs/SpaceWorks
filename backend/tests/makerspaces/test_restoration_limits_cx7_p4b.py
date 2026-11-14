"""Restoring counted definitions reacquires capacity on every authenticated client."""
from conftest import _BoundedThreadPoolExecutor as ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import close_old_connections, connection, connections
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.managed_hosting.extra_quotas import extra_used
from apps.payments.models import Payment
from tests.inventory.test_creator_limit_concurrency_cx7 import callers
from tests.makerspaces.test_people_creator_quotas_cx7 import scenario, KEYS

pytestmark = pytest.mark.django_db


def setup(key):
    space, _, model, _ = scenario(key)
    rows = []
    for index in range(2):
        values = {"makerspace": space, "name": f"Retained {index}"}
        if key == "member_units":
            values.update(slug=f"unit-{index}", code=f"U{index}", path=f"/U{index}/", archived_at=timezone.now())
        elif key == "membership_plans":
            values.update(interval="monthly", amount=0, currency="usd", archived_at=timezone.now())
        else:
            values.update(slug=f"campaign-{index}", is_active=False, currency="usd")
        rows.append(model.objects.create(**values))
    return space, model, rows


def restore(client, key, row):
    if key == "membership_plans":
        return client.delete(reverse("admin-membership-plan-archive", kwargs={"pk": row.pk}))
    if key == "member_units":
        return client.post(reverse("admin-member-unit-restore", kwargs={
            "makerspace_id": row.makerspace_id, "pk": row.pk}), {}, format="json")
    return client.patch(reverse("admin-donation-campaign", kwargs={
        "makerspace_id": row.makerspace_id, "pk": row.pk}), {"is_active": True}, format="json")


def snapshot(model):
    return (list(model.objects.order_by("pk").values()), list(AuditLog.objects.order_by("pk").values()),
            list(Payment.objects.order_by("pk").values()))


@pytest.mark.parametrize("key", KEYS)
@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
def test_restore_max_then_next_refusal_has_no_writes(key, surface, settings, monkeypatch):
    settings.MANAGED_PLANS_ENABLED = False
    space, model, rows = setup(key)
    client = callers(space, surface, settings, monkeypatch)[0]
    assert restore(client, key, rows[0]).status_code == 200
    assert extra_used(space, key) == 1
    before = snapshot(model)
    refused = restore(client, key, rows[1])
    assert (refused.status_code, refused.json()["code"]) == (409, f"{key}_quota_reached")
    assert snapshot(model) == before
    assert restore(client, key, rows[0]).status_code == 200  # no extra slot for replay
    assert extra_used(space, key) == 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("key", KEYS)
@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
def test_two_restorations_compete_for_one_slot(key, surface, settings, monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    settings.MANAGED_PLANS_ENABLED = False
    space, model, rows = setup(key)
    pair = callers(space, surface, settings, monkeypatch)
    barrier = Barrier(2)

    def worker(index):
        close_old_connections()
        try:
            if connection.vendor == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '5s'")
            barrier.wait(timeout=15)
            response = restore(pair[index], key, rows[index])
            if response.status_code == 200:
                if key == "member_units":
                    assert response.json()["code"] == rows[index].code
                return 200, None
            return response.status_code, response.json()["code"]
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker, index) for index in range(2)]
        outcomes = sorted(future.result(timeout=30) for future in futures)
    assert outcomes == [(200, None), (409, f"{key}_quota_reached")]
    assert extra_used(space, key) == 1
    action = {"member_units": "member_unit.restored", "membership_plans": "membership.plan_restored",
              "donation_campaigns": "donation.campaign_updated"}[key]
    assert AuditLog.objects.filter(makerspace=space, action=action).count() == 1
    assert model.objects.filter(makerspace=space).count() == 2
    assert Payment.objects.filter(makerspace=space).count() == 0


@pytest.mark.parametrize("key", KEYS)
@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
def test_restore_switch_off_retains_rows_then_on_reacquires_capacity(key, surface, settings, monkeypatch):
    settings.MANAGED_PLANS_ENABLED = False
    space, model, rows = setup(key)
    client = callers(space, surface, settings, monkeypatch)[0]
    field = "enabled_features" if key != "membership_plans" else "enabled_modules"
    switch = {"member_units": "membership.units", "membership_plans": "membership",
              "donation_campaigns": "finance.donations"}[key]
    saved = list(getattr(space, field))
    setattr(space, field, [value for value in saved if value != switch])
    space.save(update_fields=[field])
    before = snapshot(model)
    refused = restore(client, key, rows[0])
    assert (refused.status_code, refused.json()["code"]) == (404, "module_disabled" if field == "enabled_modules"
                                                          else "feature_disabled")
    assert snapshot(model) == before
    setattr(space, field, saved)
    space.save(update_fields=[field])
    assert restore(client, key, rows[0]).status_code == 200
    assert extra_used(space, key) == 1
    assert Payment.objects.filter(makerspace=space).count() == 0
