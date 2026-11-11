from types import SimpleNamespace

import pytest

from apps.tenant_migration.materialization_rows import _receipt_last


def model(label, fields=()):
    return SimpleNamespace(_meta=SimpleNamespace(label=label, local_concrete_fields=fields))


def test_receipt_runs_after_materialized_references_without_reordering_others():
    receipt = model("inventory.EquipmentProposalReceipt")
    use = model("inventory.EquipmentConsumableUseReceipt")
    event, booking = model("events.EventRegistration"), model("bookings.Booking")
    assert _receipt_last([event, receipt, booking, use]) == [event, booking, receipt, use]


def test_future_inbound_receipt_dependency_fails_closed():
    receipt = model("inventory.EquipmentProposalReceipt")
    use = model("inventory.EquipmentConsumableUseReceipt")
    inbound = model("inventory.FutureRecord", [SimpleNamespace(is_relation=True, related_model=receipt)])
    with pytest.raises(ValueError, match="inbound dependency"):
        _receipt_last([receipt, use, inbound])
