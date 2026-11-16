"""Admin slot consumption includes restoration and tenant moves, with roles intact."""
from copy import copy

import pytest

from apps.boxes.models import Box
from apps.inventory.models import InventoryProduct
from tests.limits_0120.admin_capacity_helpers_cx7 import bound_form, form_errors
from tests.r2_superadmin_local.helpers import superadmin
from tests.return_helpers import make_member, make_space

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("key", ["products", "boxes"])
@pytest.mark.parametrize("operation", ["restore", "move"])
def test_control_restore_and_move_consume_a_destination_slot(key, operation):
    space = make_space("cx7-target-slots")
    other = make_space("cx7-source-slots")
    actor = superadmin("cx7-slot-root")
    space.resource_limit_overrides = {key: 1}
    space.save(update_fields=["resource_limit_overrides"])
    model = InventoryProduct if key == "products" else Box
    label_field = "name" if key == "products" else "label"
    inactive_field = "is_archived" if key == "products" else "is_active"
    active_value = key == "boxes"
    model.objects.create(makerspace=space, **{label_field: "Occupant", inactive_field: active_value})
    row = model.objects.create(makerspace=space if operation == "restore" else other,
                               **{label_field: "Candidate", inactive_field: not active_value if operation == "restore" else active_value})
    changed = copy(row)
    changed.makerspace = space
    setattr(changed, inactive_field, active_value)
    form, _, _, _ = bound_form(changed, actor, instance=row)
    assert form.is_valid() is False
    assert [code for code, _ in form_errors(form)] == ["limit_reached" if key == "products" else "boxes_quota_reached"]
    row.refresh_from_db()
    assert row.makerspace_id == (space.pk if operation == "restore" else other.pk)
    assert getattr(row, inactive_field) is (not active_value if operation == "restore" else active_value)


def test_capacity_adapter_keeps_control_superadmin_only():
    space = make_space("cx7-control-role")
    actor = make_member("cx7-control-member", space)
    row = InventoryProduct(makerspace=space, name="Denied")
    _, model_admin, request, _ = bound_form(row, actor)
    assert model_admin.has_add_permission(request) is False
    assert model_admin.has_change_permission(request) is False
