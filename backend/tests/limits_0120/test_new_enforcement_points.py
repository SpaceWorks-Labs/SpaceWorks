"""Decision 328a: the nine 0.12.0 keys default to none, count real rows, and refuse only the START of something new."""
import pytest

from apps.managed_hosting import extra_quotas as eq
from tests.open_items_0120.test_platform_credential_limits import _limit
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db
KEYS = ("hardware_requests_monthly", "stock_transfers_monthly", "stocktake_sessions_monthly", "reimbursement_claims_monthly",
        "public_page_assets", "scheduled_reports", "adapter_media_bytes", "adapter_telemetry_points", "anthias_players", "shelf_checks_monthly")


@pytest.fixture(autouse=True)
def _off(settings):
    settings.PLATFORM_DOMAIN_SUFFIX = ""
    settings.MANAGED_PLANS_ENABLED = False


@pytest.mark.parametrize("key", KEYS)
def test_unlimited_by_default_and_counts_zero_on_an_empty_space(key):
    space = make_space(f"ne-{key[:24]}")
    eq.check_extra_quota(space, key, adding=10 ** 9)
    assert eq.extra_used(space, key) == 0
    assert eq.SPECS[key][0] == ("bytes" if key == "adapter_media_bytes" else "count")


@pytest.mark.parametrize("key", KEYS)
def test_a_zero_limit_refuses_the_start_with_the_typed_409_and_a_message_naming_the_limit(key):
    space = make_space(f"ne0-{key[:23]}")
    _limit(space, **{key: 0})
    with pytest.raises(eq.ExtraQuotaReached) as raised:
        eq.check_extra_quota(space, key)
    assert raised.value.status_code == 409 and raised.value.code == f"{key}_quota_reached"
    assert str(raised.value.detail["limit"]) == "0" and "platform operator" in str(raised.value.detail["detail"])


def test_the_seam_that_cannot_return_a_409_reports_false():
    space = make_space("ne-telemetry")
    assert eq.extra_quota_allows(space, "adapter_telemetry_points", adding=5) is True
    _limit(space, adapter_telemetry_points=3)
    assert eq.extra_quota_allows(space, "adapter_telemetry_points", adding=3) is True
    assert eq.extra_quota_allows(space, "adapter_telemetry_points", adding=4) is False


def test_stocktake_and_transfer_services_refuse_before_touching_anything():
    from apps.operations.models import StockTransfer, StocktakeSession
    from apps.operations.services_stocktake_workflow import create_stocktake
    from apps.operations.services_transfers import apply_stock_transfer
    space = make_space("ne-ops")
    _limit(space, stocktake_sessions_monthly=0, stock_transfers_monthly=0)
    with pytest.raises(eq.ExtraQuotaReached):
        create_stocktake(None, space, {})
    with pytest.raises(eq.ExtraQuotaReached):
        apply_stock_transfer(None, space, {})
    assert not StocktakeSession.objects.exists() and not StockTransfer.objects.exists()


def test_the_monthly_counters_follow_real_rows():
    from apps.operations.models import StocktakeSession
    space = make_space("ne-count")
    StocktakeSession.objects.create(makerspace=space)
    StocktakeSession.objects.create(makerspace=space, status=StocktakeSession.Status.CANCELLED)
    assert eq.extra_used(space, "stocktake_sessions_monthly") == 2  # cancelled ones still count
    _limit(space, stocktake_sessions_monthly=2)
    with pytest.raises(eq.ExtraQuotaReached):
        eq.check_extra_quota(space, "stocktake_sessions_monthly")
