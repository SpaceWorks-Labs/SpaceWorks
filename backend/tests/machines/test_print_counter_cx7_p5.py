"""527.3: one permanent print counter covers bucket and pooled creators."""
import pytest
from django.db import connection
from rest_framework.exceptions import APIException

from apps.makerspaces.limits_usage import _print_requests
from tests.machines.test_printer_bucket_limits_cx7_p4b import setup, create
from tests.limits_0120.creator_races_cx7 import race_creators

pytestmark = [pytest.mark.django_db, pytest.mark.area_machine_service, pytest.mark.area_machines]


@pytest.mark.parametrize("pooled", [False, True])
def test_print_usage_includes_bucket_jobs_without_counting_them_twice(pooled, settings):
    settings.MANAGED_PLANS_ENABLED = False
    w, _ = setup()
    w.space.resource_limit_overrides = {"print": 2}
    w.space.save(update_fields=["resource_limit_overrides"])
    create(w, 0)
    assert _print_requests(w.space) == 1
    create(w, 1, pooled=pooled)
    assert _print_requests(w.space) == 2
    with pytest.raises(APIException) as failure:
        create(w, 0, pooled=pooled)
    assert (failure.value.status_code, str(failure.value.detail["code"])) == (400, "limit_reached")
    assert _print_requests(w.space) == 2


@pytest.mark.django_db(transaction=True)
def test_bucket_and_pool_race_uses_the_shared_counter_once(settings):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    settings.MANAGED_PLANS_ENABLED = False
    w, _ = setup()
    assert race_creators(lambda index: create(w, index, pooled=bool(index))) == [(201, "created"), (400, "limit_reached")]
    assert _print_requests(w.space) == 1
