"""Decision 284 addendum: every countable per-space resource has a superadmin-settable limit, default none.

Covers the 17 new keys (typed 409 `<key>_quota_reached`), the three caveat fixes (restore does not count a
booking twice, platform wallet counts only platform-signed passes, platform push has one documented unit) and
the area-scoped read-only usage for area managers. Written, not run, by the limits-completion lane.
"""
import inspect

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.makerspaces.limit_registry import AREA_LABELS, AREA_OF, ENFORCEMENT, area_of
from apps.makerspaces.limits_core import EXTRA_QUOTA_LIMIT_KEYS, KNOWN_LIMIT_KEYS
from apps.managed_hosting import extra_quotas as eq
from apps.managed_hosting import platform_limits as pl
from apps.managed_hosting import space_quotas as sq
from tests.accounts.account_factories import make_staff
from tests.open_items_0120.test_platform_credential_limits import _limit
from tests.r2_superadmin_local.helpers import api, space as make_hosted_space, superadmin
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db
COUNT_KEYS = sorted(k for k, (unit, _label) in eq.SPECS.items() if unit == "count")
BYTE_KEYS = sorted(k for k, (unit, _label) in eq.SPECS.items() if unit == "bytes")
EXPECTED_AREA = {
    "event_registrations_monthly": "events", "shop_orders_monthly": "shop", "shop_products": "shop",
    "membership_plans": "people", "donation_campaigns": "money", "bookable_spaces": "bookings", "boxes": "inventory",
    "organizations_linked": "people", "api_requests_per_minute": "integrations",
    "analytics_connections": "integrations", "report_exports_monthly": "integrations", "kiosk_stations": "inventory",
    "devices": "machines", "machine_jobs_monthly": "machines", "machine_sessions_monthly": "machines",
    "storage_evidence_bytes": "storage", "storage_public_images_bytes": "storage", "webhook_endpoints": "integrations",
    # Added by later lanes and the 0.12.0 module sweep (decision 328a), so this map stays complete.
    "member_cards_issued_monthly": "people", "wallet_passes": "people", "member_units": "people",
    "collection_sheet_rows_monthly": "money", "staff_cards_issued_monthly": "people", "series_invites": "events",
    "checkin_lists": "events", "saved_views": "events", "hackathon_stages": "events",
    "event_badge_prints_monthly": "events", "paired_displays": "people", "adapter_bridges": "machines",
    "adapter_watch_streams": "machines", "adapter_snapshots": "machines", "adapter_artifacts": "machines",
    "photo_cutout_jobs_monthly": "people", "card_templates": "people", "hardware_requests_monthly": "inventory",
    "stock_transfers_monthly": "inventory", "stocktake_sessions_monthly": "inventory", "shelf_checks_monthly": "inventory",
    "reimbursement_claims_monthly": "events", "public_page_assets": "storage", "scheduled_reports":
    "integrations", "adapter_media_bytes": "storage", "adapter_telemetry_points": "machines", "anthias_players":
    "people",
}


@pytest.fixture
def switch_off(settings):
    settings.PLATFORM_DOMAIN_SUFFIX = ""
    settings.MANAGED_PLANS_ENABLED = False


# --- registry, default none, area grouping -------------------------------------------------------

def test_new_keys_are_known_grouped_and_the_shop_area_is_no_longer_empty():
    assert set(EXPECTED_AREA) == EXTRA_QUOTA_LIMIT_KEYS == set(eq.SPECS)
    assert EXTRA_QUOTA_LIMIT_KEYS <= KNOWN_LIMIT_KEYS
    for key, area in EXPECTED_AREA.items():
        assert area_of(key) == area and AREA_OF[key] == area and area in AREA_LABELS
        assert key in ENFORCEMENT
    assert {key for key, area in AREA_OF.items() if area == "shop"} >= {"shop_orders_monthly", "shop_products"}
    assert set(AREA_OF.values()) == set(AREA_LABELS)  # every area has at least one key now


@pytest.mark.parametrize("key", sorted(EXTRA_QUOTA_LIMIT_KEYS))
def test_every_new_key_defaults_to_none(switch_off, key):
    lab = make_space(f"lim-default-{key[:20]}")
    assert lab.resource_limit_overrides == {}
    assert sq.quota_limit(lab, key) is None
    eq.check_extra_quota(lab, key, adding=10 ** 9)  # never refuses while unlimited
    rows = {row["key"]: row for row in eq.usage_rows(lab)}
    assert rows[key]["limit"] is None and rows[key]["area"] == EXPECTED_AREA[key]
    assert rows[key]["unit"] == eq.SPECS[key][0]


# --- Nth allowed, N+1 refused with the typed 409 --------------------------------------------------

@pytest.mark.parametrize("key", [k for k in sorted(EXTRA_QUOTA_LIMIT_KEYS) if k != "api_requests_per_minute"])
def test_nth_allowed_and_next_refused_with_typed_409(switch_off, key):
    lab = make_space(f"lim-n-{key[:22]}")
    used = eq.extra_used(lab, key)
    _limit(lab, **{key: used + 1})
    eq.check_extra_quota(lab, key, adding=1)  # the Nth fits
    with pytest.raises(eq.ExtraQuotaReached) as raised:
        eq.check_extra_quota(lab, key, adding=2)  # the N+1th does not
    assert raised.value.status_code == 409 and raised.value.code == f"{key}_quota_reached"
    assert raised.value.detail["code"] == f"{key}_quota_reached" and str(raised.value.detail["limit"]) == str(used + 1)
    _limit(lab, **{key: 0})
    with pytest.raises(eq.ExtraQuotaReached):
        eq.check_extra_quota(lab, key, adding=1)  # a zero limit refuses the very first
    _limit(lab, **{key: -1})
    eq.check_extra_quota(lab, key, adding=10 ** 6)  # -1 is "no limit"


def test_total_counters_follow_real_rows(switch_off):
    from apps.boxes.models import Box
    lab = make_space("lim-box")
    _limit(lab, boxes=2)
    for label in ("A", "B"):
        eq.check_extra_quota(lab, "boxes")
        Box.objects.create(makerspace=lab, label=label)
    assert eq.extra_used(lab, "boxes") == 2
    with pytest.raises(eq.ExtraQuotaReached) as raised:
        eq.check_extra_quota(lab, "boxes")
    assert raised.value.code == "boxes_quota_reached"
    Box.objects.filter(makerspace=lab, label="A").update(is_active=False)
    eq.check_extra_quota(lab, "boxes")  # a retired box frees its place


def test_kiosk_stations_count_scanner_and_handover_only(switch_off):
    from apps.makerspaces.models_stations import Station
    lab = make_space("lim-kiosk")
    Station.objects.create(makerspace=lab, kind=Station.Kind.EVENT_CHECKIN, name="event-1")
    assert eq.extra_used(lab, "kiosk_stations") == 0
    Station.objects.create(makerspace=lab, kind=Station.Kind.SCANNER, name="Front")
    assert eq.extra_used(lab, "kiosk_stations") == 1


def test_webhook_endpoints_count_webhook_destinations_and_refuse_the_create_route(switch_off):
    from apps.integrations.models_destinations import NotificationDestination
    lab = make_hosted_space("lim-webhook-ep")
    NotificationDestination.objects.create(makerspace=lab, channel="slack", label="chat", webhook_url="x")
    assert eq.extra_used(lab, "webhook_endpoints") == 0  # only the outbound `webhook` channel counts
    _limit(lab, webhook_endpoints=1)
    client = api(make_staff(lab, username="lim-wh-boss"))
    url = reverse("admin-notification-destinations", args=[lab.pk])
    body = {"channel": "webhook", "label": "Hook", "webhook_url": "https://example.com/hook",
            "signing_secret": "s" * 24, "payload_version": 2}
    assert client.post(url, body, format="json").status_code == 201
    refused = client.post(url, {**body, "label": "Second"}, format="json")
    assert refused.status_code == 409 and refused.json()["code"] == "webhook_endpoints_quota_reached"


def test_report_exports_count_the_audit_trail(switch_off):
    lab = make_space("lim-reports")
    _limit(lab, report_exports_monthly=1)
    eq.check_extra_quota(lab, "report_exports_monthly")
    AuditLog.objects.create(action="report.downloaded", makerspace=lab, meta={"report_key": "x"})
    with pytest.raises(eq.ExtraQuotaReached):
        eq.check_extra_quota(lab, "report_exports_monthly")


def test_storage_split_checks_each_class_and_keeps_the_combined_key(switch_off):
    from apps.makerspaces import limits
    from apps.makerspaces.limits_uploads import STORAGE_CLASS_KEYS, charge_upload
    assert STORAGE_CLASS_KEYS == {"evidence": "storage_evidence_bytes", "public_image": "storage_public_images_bytes"}
    lab = make_space("lim-storage")
    _limit(lab, storage_evidence_bytes=100, storage_public_images_bytes=50, storage=10 ** 9)
    with pytest.raises(eq.ExtraQuotaReached) as raised:
        charge_upload(lab, 101, kind="evidence")
    assert raised.value.code == "storage_evidence_bytes_quota_reached"
    with pytest.raises(eq.ExtraQuotaReached) as raised:
        charge_upload(lab, 51)  # default kind = non-evidence (public images and the rest)
    assert raised.value.code == "storage_public_images_bytes_quota_reached"
    assert limits.resource_limit(lab, "storage") == 10 ** 9  # the combined key still resolves


def test_sources_call_the_check_at_every_start_seam():
    """Each seam names its key: a rename or removal fails here (the registry test checks one needle per key)."""
    import apps
    from pathlib import Path
    root = Path(apps.__file__).parent
    seams = {
        "events/services_registration.py": "event_registrations_monthly", "events/orders_checkout.py": "event_registrations_monthly",
        "events/passes.py": "event_registrations_monthly", "shop/orders_core.py": "shop_orders_monthly",
        "shop/services_catalogue.py": "shop_products", "admin_api/views_membership_plans.py": "membership_plans",
        "payments/donations/views_staff.py": "donation_campaigns", "bookings/services_spaces.py": "bookable_spaces",
        "bookings/services_clone.py": "bookable_spaces", "boxes/api_views_qr.py": "boxes",
        "organizations/services_owner.py": "organizations_linked", "organizations/services_console.py": "organizations_linked",
        "analytics/services.py": "analytics_connections", "analytics/grafana_services.py": "analytics_connections",
        "operations/report_download.py": "report_exports_monthly", "makerspaces/kiosk_station_services.py": "kiosk_stations",
        "devices/services_identity.py": "devices", "machines/service_workflow_actions.py": "machine_jobs_monthly",
        "machines/sessions_service.py": "machine_sessions_monthly", "apiclients/throttling.py": "api_requests_per_minute",
        "admin_api/views_notification_destinations.py": "webhook_endpoints",
    }
    for path, key in seams.items():
        assert f'"{key}"' in (root / path).read_text(encoding="utf-8"), (path, key)


def test_reads_exports_settling_and_privacy_paths_never_call_the_new_check():
    from apps.accounts import account_purge
    from apps.data_export import subject_services
    from apps.hardware_requests import workflow
    from apps.payments import offline_claims, reconciliation, services
    for module in (account_purge, subject_services, workflow, offline_claims, reconciliation):
        assert "extra_quotas" not in inspect.getsource(module), module.__name__
    assert "extra_quotas" not in inspect.getsource(services.create_payment)


# --- API requests per minute: may only LOWER the tier rate --------------------------------------

def test_api_rate_override_only_lowers_the_tier_rate(switch_off):
    from apps.apiclients.models import ApiClient
    from apps.apiclients.throttling import ClientTierRateThrottle
    lab = make_space("lim-rate")
    client = ApiClient(makerspace=lab, client_id="c1", rate_limit_tier="standard")
    throttle = ClientTierRateThrottle()
    throttle.num_requests, throttle.duration = 60, 60
    throttle._apply_space_limit(client)
    assert (throttle.num_requests, throttle.duration) == (60, 60)  # default: current behaviour
    _limit(lab, api_requests_per_minute=10)
    throttle._apply_space_limit(client)
    assert (throttle.num_requests, throttle.duration) == (10, 60)
    _limit(lab, api_requests_per_minute=500)
    throttle.num_requests, throttle.duration = 60, 60
    throttle._apply_space_limit(client)
    assert (throttle.num_requests, throttle.duration) == (60, 60)  # never raises the tier rate
    assert eq.api_rate_limit(lab) == 500


# --- caveats ------------------------------------------------------------------------------------

def test_restoring_a_cancelled_booking_does_not_count_twice(switch_off):
    from apps.makerspaces.limits import check_quota
    lab = make_space("lim-restore")
    _limit(lab, bookings_monthly=0)
    with pytest.raises(sq.SpaceQuotaReached):
        check_quota(lab, "bookings", adding=1)  # a NEW booking is refused
    check_quota(lab, "bookings", adding=1, count_monthly=False)  # a restore skips the monthly quota only
    from apps.bookings import services_restore
    assert "count_monthly=False" in inspect.getsource(services_restore)


def test_publishing_a_draft_created_this_month_adds_nothing_to_events_monthly(switch_off):
    from apps.makerspaces.limits import check_quota
    from tests.events.orders_helpers import ticketed_event
    lab = make_space("lim-publish")
    ticketed_event(lab)  # counted at creation
    _limit(lab, events_monthly=1)
    check_quota(lab, "events", adding=1, monthly_adding=0)  # publishing it again: already counted
    with pytest.raises(sq.SpaceQuotaReached):
        check_quota(lab, "events", adding=1)  # a second event this month is refused


def test_platform_wallet_counts_only_platform_signed_passes(switch_off):
    from apps.card_designs.models import WalletPass
    from apps.card_designs.wallet.credentials import auth_token, digest
    from apps.makerspaces import member_card_services as services
    from tests.l3_local.helpers import card_space, manager, member
    lab = card_space("lim-wallet")
    card = services.issue_card(manager(lab), member(lab)[0])
    own = WalletPass.objects.create(makerspace=lab, member_card=card, platform="apple", serial="own1",
                                    auth_token_digest=digest(auth_token("own1")))
    platform = WalletPass.objects.create(makerspace=lab, member_card=card, platform="google", serial="plat1",
                                         auth_token_digest=digest(auth_token("plat1")))
    for row, source in ((own, "own"), (platform, "platform")):
        AuditLog.objects.create(action="wallet_pass.issued", makerspace=lab,
                                meta={"pass_id": row.pk, "platform": row.platform, "source": source})
    assert pl.platform_used(lab, "platform_wallet_monthly") == 1  # the own-certificate pass is never counted
    from apps.card_designs.wallet import service
    assert '"source"' in inspect.getsource(service.issue_from_job)  # stamped at issue time


def test_platform_push_has_one_documented_unit(switch_off):
    lab = make_space("lim-push")
    assert pl.platform_used(lab, "platform_push_monthly") == 0
    source = inspect.getsource(pl.platform_used)
    assert "PushDeliveryAttempt" in source and "ONE PUSH DELIVERY" in source


# --- superadmin GET/PUT/bulk return and accept every key, grouped by area -------------------------

def test_superadmin_get_put_and_bulk_cover_every_new_key(switch_off):
    lab, other = make_hosted_space("lim-api"), make_hosted_space("lim-api-2")
    client = api(superadmin("lim-root"))
    url = reverse("admin-space-limits", args=[lab.pk])
    body = client.get(url).json()
    rows = {row["key"]: row for row in body["quota_rows"]}
    assert EXTRA_QUOTA_LIMIT_KEYS <= set(rows)
    assert all(rows[key]["area"] == EXPECTED_AREA[key] for key in EXTRA_QUOTA_LIMIT_KEYS)
    assert {area["key"] for area in body["areas"]} == set(AREA_LABELS)
    every = {key: 5 for key in EXTRA_QUOTA_LIMIT_KEYS}
    assert client.put(url, {"overrides": every}, format="json").status_code == 200
    lab.refresh_from_db()
    assert lab.resource_limit_overrides == every
    bulk = client.post(reverse("admin-platform-space-limits-bulk"),
                       {"makerspace_ids": [lab.pk, other.pk], "set": {key: 3 for key in EXTRA_QUOTA_LIMIT_KEYS},
                        "clear": ["boxes"]}, format="json")
    assert bulk.status_code == 200, bulk.content
    other.refresh_from_db()
    assert other.resource_limit_overrides["shop_products"] == 3 and "boxes" not in other.resource_limit_overrides
    assert client.put(url, {"overrides": {"not_a_key": 1}}, format="json").status_code == 400


# --- area managers see usage for their own area's keys, read-only -----------------------------------

def test_area_managers_see_their_areas_new_keys_and_never_the_rest(switch_off):
    from apps.managed_hosting.limits_role import allowance_rows
    lab = make_hosted_space("lim-area", resource_limit_overrides={
        "storage_evidence_bytes": 1000, "machine_jobs_monthly": 5, "devices": 2, "api_requests_per_minute": 30,
        "event_registrations_monthly": 9, "shop_products": 4})
    inventory = make_staff(lab, username="lim-inv", role_slug="inventory_manager")
    machines = make_staff(lab, username="lim-mach", role_slug="machine_manager")
    boss = make_staff(lab, username="lim-boss")
    inv_keys = {row["key"] for row in allowance_rows(inventory, lab)["rows"]}
    mach_keys = {row["key"] for row in allowance_rows(machines, lab)["rows"]}
    boss_keys = {row["key"] for row in allowance_rows(boss, lab)["rows"]}
    assert "storage_evidence_bytes" in inv_keys and "machine_jobs_monthly" not in inv_keys
    assert "machine_jobs_monthly" in mach_keys and "api_requests_per_minute" not in mach_keys
    assert "api_requests_per_minute" not in inv_keys and "api_requests_per_minute" not in mach_keys
    assert {"storage_evidence_bytes", "machine_jobs_monthly", "devices", "api_requests_per_minute",
            "event_registrations_monthly", "shop_products"} <= boss_keys  # the Space Manager sees every key
    row = next(r for r in allowance_rows(boss, lab)["rows"] if r["key"] == "api_requests_per_minute")
    assert row["unit"] == "per_minute" and row["used"] is None and row["remaining"] is None
    client = APIClient()
    client.force_authenticate(inventory)
    assert client.put(reverse("admin-space-limits", args=[lab.pk]), {"overrides": {}},
                      format="json").status_code == 403  # read-only: an area manager never writes limits
