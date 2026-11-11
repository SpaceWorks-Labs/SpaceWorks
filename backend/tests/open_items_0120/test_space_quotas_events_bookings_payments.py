"""Owner 2026-11-11: per-space monthly quotas for events, bookings and payments; default none, every space."""
import inspect

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.makerspaces.limit_registry import AREA_LABELS, AREA_OF, ENFORCEMENT, area_of
from apps.makerspaces.limits_core import KNOWN_LIMIT_KEYS, SPACE_QUOTA_LIMIT_KEYS
from apps.managed_hosting import platform_limits as pl
from apps.managed_hosting import space_quotas as sq
from tests.accounts.reauth_helpers import force_recent_authenticate
from tests.open_items_0120.test_platform_credential_limits import _connect_charge, _limit
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db


@pytest.fixture
def switch_off(settings):
    settings.PLATFORM_DOMAIN_SUFFIX = ""
    settings.MANAGED_PLANS_ENABLED = False


def _root(name="sq-root"):
    return User.objects.create_user(username=name, password="Root password 77!", account_kind="platform",
                                    role=User.Role.SUPERADMIN, is_superuser=True, is_staff=True)


def test_every_quota_key_defaults_to_none(switch_off):
    space = make_space("sq-default")
    assert space.resource_limit_overrides == {}
    for key in sorted(sq.SPACE_QUOTA_KEYS):
        assert sq.quota_limit(space, key) is None
        sq.check_space_quota(space, key, adding=10 ** 6)  # never raises while unlimited
    assert SPACE_QUOTA_LIMIT_KEYS == sq.SPACE_QUOTA_KEYS
    assert SPACE_QUOTA_LIMIT_KEYS <= KNOWN_LIMIT_KEYS


def test_event_quota_nth_allowed_and_next_refused_with_typed_409(switch_off):
    from apps.makerspaces.limits import check_quota
    from tests.events.orders_helpers import ticketed_event
    space = make_space("sq-events")
    _limit(space, events_monthly=1)
    check_quota(space, "events", adding=1)  # the first one fits
    ticketed_event(space)
    with pytest.raises(sq.SpaceQuotaReached) as raised:
        check_quota(space, "events", adding=1)
    assert raised.value.status_code == 409 and raised.value.code == "event_quota_reached"


def test_booking_quota_refuses_with_typed_409(switch_off):
    from apps.makerspaces.limits import check_quota
    space = make_space("sq-bookings")
    check_quota(space, "bookings", adding=1)  # unlimited by default
    _limit(space, bookings_monthly=0)
    with pytest.raises(sq.SpaceQuotaReached) as raised:
        check_quota(space, "bookings", adding=1)
    assert raised.value.code == "booking_quota_reached"


def test_payment_quota_blocks_a_new_paid_transaction_only(switch_off):
    space = make_space("sq-pay")
    _limit(space, payments_monthly_count=0)
    with pytest.raises(sq.SpaceQuotaReached) as raised:
        sq.require_payment_capacity(space, 10, "usd")
    assert raised.value.code == "payment_quota_reached" and raised.value.status_code == 409
    _limit(space, payments_monthly_count=None, payments_monthly_amount=5)
    with pytest.raises(sq.SpaceQuotaReached):
        sq.require_payment_capacity(space, 6, "usd")
    sq.require_payment_capacity(space, 5, "usd")  # exactly the allowance still fits


def test_ledger_offline_and_refunds_are_never_gated(switch_off):
    """create_payment, offline settlement and refunds never read the quota; a pending charge stays payable."""
    from apps.payments import offline_claims, reconciliation, services
    assert "space_quotas" not in inspect.getsource(services.create_payment)
    assert "space_quotas" not in inspect.getsource(offline_claims) + inspect.getsource(reconciliation)
    space, _staff, payment = _connect_charge("sq-ledger")
    _limit(space, payments_monthly_count=0, payments_monthly_amount=0, platform_payments_monthly_count=1)
    assert pl.rail_refusal(space, payment) is None  # pending charge: still payable on the platform rail


def test_platform_rail_refuses_only_a_charge_raised_after_the_quota_was_reached(switch_off):
    space, _staff, payment = _connect_charge("sq-after")
    _limit(space, platform_payments_monthly_count=0)
    assert pl.rail_refusal(space, payment)  # it was the first charge past a zero allowance
    AuditLog.objects.create(action="space_control.limits_changed", makerspace=space,
                            meta={"changed": ["platform_payments_monthly_count"], "overrides": {}})
    assert pl.rail_refusal(space, payment) is None  # limit set AFTER the charge was raised: spared


def test_superadmin_edits_bulk_clears_and_audits(switch_off):
    one, two = make_space("sq-bulk-1"), make_space("sq-bulk-2")
    client = APIClient()
    force_recent_authenticate(client, _root())
    url = reverse("admin-space-limits", args=[one.pk])
    assert client.put(url, {"overrides": {"events_monthly": 3, "payments_monthly_amount": 100}},
                      format="json").status_code == 200
    one.refresh_from_db()
    assert one.resource_limit_overrides == {"events_monthly": 3, "payments_monthly_amount": 100}
    body = client.get(url).json()
    from apps.makerspaces.limits_core import EXTRA_QUOTA_LIMIT_KEYS  # decision 284 addendum: every other key too
    assert {row["key"] for row in body["quota_rows"]} == set(sq.SPACE_QUOTA_KEYS) | EXTRA_QUOTA_LIMIT_KEYS
    assert {area["key"] for area in body["areas"]} == set(AREA_LABELS)
    bulk = reverse("admin-platform-space-limits-bulk")
    done = client.post(bulk, {"makerspace_ids": [one.pk, two.pk], "set": {"bookings_monthly": 7},
                              "clear": ["events_monthly"]}, format="json")
    assert done.status_code == 200 and done.json()["updated"] == 2
    one.refresh_from_db()
    two.refresh_from_db()
    assert one.resource_limit_overrides == {"payments_monthly_amount": 100, "bookings_monthly": 7}
    assert two.resource_limit_overrides == {"bookings_monthly": 7}
    assert AuditLog.objects.filter(action="space_control.limits_changed", makerspace=two).count() == 1
    refused = client.post(bulk, {"makerspace_ids": [two.pk, 10 ** 9], "set": {"events_monthly": 1}}, format="json")
    assert refused.status_code == 409 and refused.json()["code"] == "bulk_failed"
    two.refresh_from_db()
    assert "events_monthly" not in two.resource_limit_overrides  # all or nothing
    assert client.post(bulk, {"makerspace_ids": list(range(1, 52)), "set": {"events_monthly": 1}},
                       format="json").status_code == 400  # at most 50
    assert client.put(url, {"overrides": {}}, format="json").status_code == 200  # reset to none
    one.refresh_from_db()
    assert one.resource_limit_overrides == {}


def test_space_manager_sees_usage_read_only_and_cannot_write(switch_off):
    from tests.makerspaces.l4_helpers import space_with_manager
    space, manager = space_with_manager("sq-sm")
    _limit(space, events_monthly=4)
    client = APIClient()
    client.force_authenticate(manager)
    usage = client.get(reverse("admin-makerspace-hosting-plan", args=[space.pk]))
    assert usage.status_code == 200
    rows = {row["key"]: row for row in usage.json()["space_quota_resources"]}
    assert rows["events_monthly"]["limit"] == 4 and rows["bookings_monthly"]["limit"] is None
    assert set(usage.json()["platform_switches"]) == {"email", "sms", "whatsapp", "native_push", "wallet"}
    assert client.put(reverse("admin-space-limits", args=[space.pk]), {"overrides": {}},
                      format="json").status_code == 403
    assert client.post(reverse("admin-platform-space-limits-bulk"),
                       {"makerspace_ids": [space.pk], "set": {"events_monthly": 1}}, format="json").status_code == 403


def test_override_applies_to_an_own_space_for_every_existing_key(switch_off):
    from apps.makerspaces.limits_core import resource_limit
    space = make_space("sq-own")
    assert resource_limit(space, "products") is None
    _limit(space, products=3)
    assert resource_limit(space, "products") == 3  # a limit the superadmin set applies to an own space too


# --- registry coverage guard ----------------------------------------------------------------

def test_every_known_key_has_an_area_and_a_real_enforcement_point():
    from pathlib import Path

    import apps
    root = Path(apps.__file__).parent
    assert set(ENFORCEMENT) == set(KNOWN_LIMIT_KEYS), set(KNOWN_LIMIT_KEYS) ^ set(ENFORCEMENT)
    for key, (path, needle) in ENFORCEMENT.items():
        assert needle in (root / path).read_text(encoding="utf-8"), (key, path, needle)
        assert area_of(key) in AREA_LABELS
    assert set(AREA_OF.values()) <= set(AREA_LABELS)
