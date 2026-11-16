"""MI-40: consumables raise one automatic To-Buy at their reorder point, and a received
To-Buy credits its origin."""

from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from apps.audit.models import AuditLog
from apps.inventory import availability
from apps.inventory.models import InventoryProduct, TrackingMode
from apps.procurement import services
from apps.procurement.models import ToBuyItem
from tests.return_helpers import make_member, make_product
from tests.return_helpers import make_space as _make_space

pytestmark = pytest.mark.django_db
TOBUY = ("inventory.tobuy", "machines.tobuy")


def make_space(slug, features=TOBUY):
    space = _make_space(slug)
    space.enabled_features = sorted(set(space.enabled_features or []) | set(features))
    space.save(update_fields=["enabled_features"])
    return space


def consumable(space, **overrides):
    values = {"available_quantity": 10, "total_quantity": 10, "is_consumable": True,
              "reorder_point": 3, "reorder_quantity": 20, "supplier": "Screw Co", "is_public": False}
    values.update(overrides)
    return make_product(space, name="M3 screws", **values)


def use(actor, product, quantity):
    return availability.consume_available(product, quantity, reason="used", actor=actor)


def test_crossing_the_reorder_point_creates_exactly_one_system_draft(django_capture_on_commit_callbacks):
    space = make_space("auto-buy")
    actor = make_member("auto-buy-staff", space)
    product = consumable(space)
    with django_capture_on_commit_callbacks(execute=True):
        product = use(actor, product, 7)
    items = list(ToBuyItem.objects.filter(source_product=product))
    assert len(items) == 1
    item = items[0]
    assert (item.kind, item.status, item.quantity, item.created_by) == ("hardware", "requested", 20, None)
    assert item.vendor_name == "Screw Co"
    assert AuditLog.objects.filter(action="procurement.auto_tobuy_created", target_id=str(item.pk)).count() == 1
    with django_capture_on_commit_callbacks(execute=True):
        use(actor, product, 1)
    assert ToBuyItem.objects.filter(source_product=product).count() == 1


def test_non_consumables_and_disabled_procurement_never_draft(django_capture_on_commit_callbacks):
    space = make_space("auto-buy-off")
    actor = make_member("auto-buy-off-staff", space)
    lent = make_product(space, available_quantity=10, total_quantity=10, reorder_point=3, reorder_quantity=5)
    with django_capture_on_commit_callbacks(execute=True):
        use(actor, lent, 8)
    assert not ToBuyItem.objects.filter(source_product=lent).exists()
    # Each parent's switch hides only its own rows (#128 C-9).
    space.enabled_features = [key for key in space.enabled_features if key != "inventory.tobuy"]
    space.save(update_fields=["enabled_features"])
    product = consumable(space)
    with django_capture_on_commit_callbacks(execute=True):
        use(actor, product, 8)
    assert not ToBuyItem.objects.filter(source_product=product).exists()


def test_draft_failure_never_undoes_the_stock_change(monkeypatch, django_capture_on_commit_callbacks):
    space = make_space("auto-buy-fail")
    actor = make_member("auto-buy-fail-staff", space)
    product = consumable(space)
    monkeypatch.setattr("apps.procurement.auto_drafts._open", lambda **kw: 1 / 0)
    with django_capture_on_commit_callbacks(execute=True):
        product = use(actor, product, 8)
    product.refresh_from_db()
    assert product.available_quantity == 2
    assert not ToBuyItem.objects.filter(source_product=product).exists()


def test_consumables_must_be_quantity_tracked():
    space = make_space("auto-buy-check")
    with pytest.raises(IntegrityError), transaction.atomic():
        make_product(space, is_consumable=True, tracking_mode=TrackingMode.INDIVIDUAL)


def test_received_restock_tops_up_its_source_product_only(django_capture_on_commit_callbacks):
    space = make_space("auto-buy-refill")
    actor = make_member("auto-buy-refill-staff", space)
    product = consumable(space)
    other = make_product(space, name="Other")
    with django_capture_on_commit_callbacks(execute=True):
        product = use(actor, product, 8)
    item = ToBuyItem.objects.get(source_product=product)
    item.status = ToBuyItem.Status.RECEIVED
    item.save(update_fields=["status"])
    kwargs = dict(mode="topup", quantity=20, is_public=False, public_availability_mode="status_only",
                  show_public_count=False, public_self_checkout_enabled=False)
    from rest_framework.exceptions import ValidationError
    with pytest.raises(ValidationError):
        services.move_to_inventory(actor, item, product_id=other.pk, **kwargs)
    services.move_to_inventory(actor, item, **kwargs)
    product.refresh_from_db()
    assert product.available_quantity == 22
    item.refresh_from_db()
    assert item.resulting_product_id == product.pk


def test_grams_consumable_drafts_and_refills_once(django_capture_on_commit_callbacks):
    from apps.machines.models import Machine, MachineConsumable, MachineType
    from apps.machines.services_consumables import log_consumption, unlink_consumable
    from apps.procurement.services_refill import refill_consumable
    from rest_framework.exceptions import ValidationError
    space = make_space("auto-buy-grams")
    actor = make_member("auto-buy-grams-staff", space)
    machine_type = MachineType.objects.get(makerspace__isnull=True, slug="laser_cutter")
    machine = Machine.objects.create(makerspace=space, machine_type=machine_type, name="Laser")
    row = MachineConsumable.objects.create(machine=machine, measurement="grams", label="Lens wipes",
                                           remaining=Decimal("50"), low_threshold=Decimal("10"))
    with django_capture_on_commit_callbacks(execute=True):
        log_consumption(machine, actor, row, Decimal("45"))
    item = ToBuyItem.objects.get(source_consumable=row)
    assert item.machine_type_id == machine_type.pk
    assert item.kind == ToBuyItem.Kind.PRINTING  # a machine row, under machines.tobuy
    with pytest.raises(ValidationError):
        unlink_consumable(machine, actor, row)
    with pytest.raises(ValidationError):
        refill_consumable(actor, item, Decimal("100"))
    item.status = ToBuyItem.Status.RECEIVED
    item.save(update_fields=["status"])
    refill_consumable(actor, item, Decimal("100"))
    row.refresh_from_db()
    assert row.remaining == Decimal("105")
    with pytest.raises(ValidationError):
        refill_consumable(actor, item, Decimal("100"))
    assert AuditLog.objects.filter(action="procurement.consumable_refilled").count() == 1


def test_consumables_are_not_lendable():
    from apps.hardware_requests.request_workflow import RequesterSnapshot, submit_request
    from apps.hardware_requests.workflow_errors import RequestValidationError
    from tests.return_helpers import make_user
    space = make_space("auto-buy-lend")
    space.enabled_features = sorted(set(space.enabled_features or []) | {"loans.enabled"})
    space.save(update_fields=["enabled_features"])
    product = consumable(space, is_public=True)
    member = make_user("auto-buy-lender", access_status="active")
    snapshot = RequesterSnapshot(username=member.username, name="", email="", phone="")
    with pytest.raises(RequestValidationError):
        submit_request(space, [{"product": product, "quantity": 1}], requester_principal=member,
                       contact_snapshot=snapshot, audit_actor=member)
    assert InventoryProduct.objects.get(pk=product.pk).available_quantity == 10
