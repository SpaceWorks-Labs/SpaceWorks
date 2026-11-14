"""Capacity at the actual registered admin forms, including the last-slot race."""
from conftest import _BoundedThreadPoolExecutor as ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import close_old_connections, connection, transaction, connections

from apps.makerspaces.admin_limits import form_limit_error
from apps.makerspaces.limits_usage import _COUNTERS
from apps.managed_hosting.extra_quotas import ExtraQuotaReached, extra_used
from rest_framework.exceptions import ValidationError
from tests.limits_0120.admin_capacity_helpers_cx7 import bound_form, form_errors, prepare, row_for
from tests.r2_superadmin_local.helpers import superadmin
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db
CASES = [
    pytest.param("products", marks=pytest.mark.area_inventory),
    pytest.param("assets", marks=pytest.mark.area_inventory),
    pytest.param("machines", marks=pytest.mark.area_machines),
    pytest.param("boxes", marks=pytest.mark.area_inventory),
    pytest.param("api_clients", marks=pytest.mark.area_auth),
    pytest.param("webhook_endpoints", marks=pytest.mark.area_notifications),
    pytest.param("stocktake_sessions_monthly", marks=pytest.mark.area_inventory),
]


def used(space, key):
    return _COUNTERS[key](space) if key in _COUNTERS else extra_used(space, key)


def expected_error(space, key):
    if key in _COUNTERS:
        from apps.makerspaces.limits import check_quota

        with pytest.raises(ValidationError) as raised, transaction.atomic():
            check_quota(space, key)
        assert raised.value.status_code == 400
        assert str(raised.value.detail["code"]) == "limit_reached"
        return form_limit_error(raised.value)
    error = ExtraQuotaReached(key, 1)
    assert error.status_code == 409
    assert str(error.detail["code"]) == f"{key}_quota_reached"
    return form_limit_error(error)


@pytest.mark.parametrize("key", CASES)
@pytest.mark.parametrize("suffix", ["", ".space-works.tech"])
def test_registered_control_form_max_next_error_edit_and_override(key, suffix, settings):
    settings.PLATFORM_DOMAIN_SUFFIX = suffix
    settings.MANAGED_PLANS_ENABLED = False
    space = make_space("cx7-control-capacity")
    actor = superadmin("cx7-control-root")
    prepare(key, space)
    space.resource_limit_overrides = {key: 1}
    space.save(update_fields=["resource_limit_overrides"])
    first = row_for(key, space, "Last")
    with transaction.atomic():
        form, model_admin, request, _ = bound_form(first, actor)
        assert model_admin.has_add_permission(request) is True
        assert form.is_valid(), form.errors
        model_admin.save_model(request, form.save(commit=False), form, False)
    assert used(space, key) == 1
    refused, _, _, _ = bound_form(row_for(key, space, "Excess"), actor)
    assert refused.is_valid() is False
    error = expected_error(space, key)
    assert form_errors(refused) == [(error.code, error.message)]
    assert used(space, key) == 1
    first.refresh_from_db()
    edit, _, _, _ = bound_form(first, actor, instance=first)
    assert edit.is_valid(), edit.errors
    # The platform operator's explicit increase restores the same form.
    space.resource_limit_overrides = {key: 2}
    space.save(update_fields=["resource_limit_overrides"])
    second, model_admin, request, _ = bound_form(row_for(key, space, "Excess"), actor)
    with transaction.atomic():
        assert second.is_valid(), second.errors
        model_admin.save_model(request, second.save(commit=False), second, False)
    assert used(space, key) == 2


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("key", CASES)
def test_two_control_creators_at_max_minus_one_admit_exactly_one(key, settings):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    settings.MANAGED_PLANS_ENABLED = False
    space = make_space("cx7-control-race")
    actor = superadmin("cx7-control-race-root")
    prepare(key, space)
    space.resource_limit_overrides = {key: 1}
    space.save(update_fields=["resource_limit_overrides"])
    barrier = Barrier(2)

    def create(label):
        close_old_connections()
        try:
            if connection.vendor == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '5s'")
            form, model_admin, request, _ = bound_form(row_for(key, space, label), actor)
            barrier.wait(timeout=15)
            # Django's changeform POST holds this transaction through validation
            # and saving; each worker uses its own connection and a real form.
            with transaction.atomic():
                if not form.is_valid():
                    return ("refused", form_errors(form))
                row = form.save(commit=False)
                model_admin.save_model(request, row, form, False)
                return ("saved", [])
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(create, label) for label in ("A", "B")]
        results = [future.result(timeout=30) for future in futures]
    assert used(space, key) == 1
    error = expected_error(space, key)
    assert sorted(results) == [("refused", [(error.code, error.message)]), ("saved", [])]
