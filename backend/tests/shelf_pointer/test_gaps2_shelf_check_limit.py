"""Decision 337e: the monthly shelf-check limit (default off) refuses only a NEW check; counters follow real rows."""
import pytest
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.devices.models import ShelfCheck
from apps.managed_hosting import extra_quotas as eq
from tests.open_items_0120.test_platform_credential_limits import _limit
from tests.shelf_pointer.pointer_case import pointer_case

pytestmark = pytest.mark.django_db(transaction=True)
BODY = {"scope_label": "Shelf *", "entries": [{"location": "Shelf A", "status": "ok"}]}


def _url(case):
    return reverse("devices:admin-shelf-checks", args=[case["space"].pk])


def test_unlimited_by_default_and_counted_when_a_limit_is_set():
    case = pointer_case("sc-limit-default")
    assert case["client"].post(_url(case), BODY, format="json").status_code == 201
    assert case["client"].post(_url(case), BODY, format="json").status_code == 201
    assert eq.extra_used(case["space"], "shelf_checks_monthly") == 2


def test_a_reached_limit_refuses_the_next_check_with_the_typed_409_and_writes_nothing():
    case = pointer_case("sc-limit-reached")
    _limit(case["space"], shelf_checks_monthly=1)
    assert case["client"].post(_url(case), BODY, format="json").status_code == 201
    refused = case["client"].post(_url(case), BODY, format="json")
    assert refused.status_code == 409 and refused.data["code"] == "shelf_checks_monthly_quota_reached"
    assert ShelfCheck.objects.filter(makerspace=case["space"]).count() == 1
    assert AuditLog.objects.filter(action="devices.shelf_check_saved").count() == 1
    # Reading past checks is never limited.
    assert case["client"].get(_url(case)).data["count"] == 1
