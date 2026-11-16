"""Every shared numeric quota refusal has a status, machine code and display message."""
import pytest

from apps.makerspaces.limits_usage import _COUNTERS
from tests.return_helpers import authenticated_client, make_member, make_space

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("key", sorted(_COUNTERS))
@pytest.mark.parametrize("suffix", ["", ".space-works.tech"])
def test_each_numeric_counter_accepts_max_and_returns_a_typed_error_above_it(settings, key, suffix):
    from django.db import transaction
    from apps.hardware_requests.exceptions import workflow_exception_handler
    from apps.makerspaces.limits import check_quota
    from rest_framework.exceptions import ValidationError
    settings.PLATFORM_DOMAIN_SUFFIX = suffix
    settings.MANAGED_PLANS_ENABLED = False
    space = make_space("cx7-counter-boundary")
    current = _COUNTERS[key](space)
    space.resource_limit_overrides = {key: current + 1}
    space.save(update_fields=["resource_limit_overrides"])
    with transaction.atomic():
        assert check_quota(space, key, adding=1) is None
    with pytest.raises(ValidationError) as raised, transaction.atomic():
        check_quota(space, key, adding=2)
    response = workflow_exception_handler(raised.value, {})
    assert response.status_code == 400
    assert response.data["code"] == "limit_reached"
    assert response.data["detail"] == response.data["limit"]
    assert _COUNTERS[key](space) == current


def test_inventory_creation_accepts_the_limit_and_refuses_the_next_row(settings):
    settings.MANAGED_PLANS_ENABLED = False
    space = make_space("cx7-inventory-limit")
    space.resource_limit_overrides = {"products": 1}
    space.save(update_fields=["resource_limit_overrides"])
    actor = make_member("cx7-limit-manager", space)
    client = authenticated_client(actor)
    from django.urls import reverse
    from apps.inventory.models import InventoryProduct
    url = reverse("admin-inventory", kwargs={"makerspace_id": space.pk})
    body = {"name": "One tool", "total_quantity": 1, "available_quantity": 1}
    allowed = client.post(url, body, format="json")
    assert allowed.status_code == 201
    refused = client.post(url, {**body, "name": "One too many"}, format="json")
    assert refused.status_code == 400
    assert refused.json()["code"] == "limit_reached"
    assert refused.json()["detail"] == refused.json()["limit"]
    assert "products" in refused.json()["detail"]
    assert InventoryProduct.objects.filter(makerspace=space).count() == 1


def test_upload_cap_has_the_same_typed_message_before_and_after_upload():
    from apps.hardware_requests.exceptions import workflow_exception_handler
    from apps.makerspaces.limits_uploads import charge_upload, check_upload_headroom, check_upload_size
    from rest_framework.exceptions import ValidationError
    space = make_space("cx7-upload-limit")
    space.resource_limit_overrides = {"upload_bytes": 1024}
    space.save(update_fields=["resource_limit_overrides"])
    assert check_upload_size(space, 1024) is None
    assert check_upload_headroom(space, 1024) is None
    assert charge_upload(space, 1024) is None
    space.refresh_from_db()
    assert space.storage_bytes_used == 1024
    bodies = []
    for check in (check_upload_size, charge_upload):
        with pytest.raises(ValidationError) as raised:
            check(space, 1025)
        response = workflow_exception_handler(raised.value, {})
        assert response.status_code == 400
        assert response.data["code"] == "upload_limit"
        assert response.data["detail"] == response.data["limit"]
        bodies.append(response.data)
    assert bodies[0] == bodies[1]


def test_locked_storage_accounting_accepts_max_and_refuses_one_more_byte():
    from apps.hardware_requests.exceptions import workflow_exception_handler
    from apps.makerspaces.limits_usage import add_storage
    from rest_framework.exceptions import ValidationError
    space = make_space("cx7-storage-boundary")
    space.resource_limit_overrides = {"storage": 1024}
    space.save(update_fields=["resource_limit_overrides"])
    add_storage(space, 1024)
    with pytest.raises(ValidationError) as raised:
        add_storage(space, 1)
    response = workflow_exception_handler(raised.value, {})
    assert response.status_code == 400
    assert response.data["code"] == "limit_reached"
    assert response.data["detail"] == response.data["limit"]
    space.refresh_from_db()
    assert space.storage_bytes_used == 1024
