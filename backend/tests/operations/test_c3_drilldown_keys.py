"""Lane C3 (decision 242, IN7/MC10): ledger drill-down keys and the incident register's saved views."""

from datetime import datetime, timezone

from apps.accounts import rbac
from apps.admin_api.staff_list_scope import ENTITY_ACTIONS
from apps.audit.areas import READER_ACTIONS
from apps.operations.ledger_units import _public_row
from apps.operations.serializers import LedgerRowSerializer


def _raw(**overrides):
    row = {
        "ledger_source": "request", "ledger_item_name": "Multimeter", "ledger_container": None, "quantity": 1,
        "ledger_target_label": None, "since": datetime(2026, 11, 1, tzinfo=timezone.utc), "due": None,
        "ledger_makerspace_id": 4, "reference_id": 31, "ledger_status": "issued", "ledger_request_id": 31,
        "ledger_product_id": 5, "holder_sort_id": 9, "ledger_item_id": 70, "loan_id": None,
    }
    row.update(overrides)
    return row


def test_ledger_row_carries_request_product_and_holder_ids():
    row = _public_row(_raw(), {31: "Asha"}, {})
    assert (row["request_id"], row["product_id"], row["holder_id"]) == (31, 5, 9)
    assert row["holder"] == "Asha"
    assert LedgerRowSerializer(row).data["request_id"] == 31


def test_container_only_rows_have_no_product():
    row = _public_row(_raw(ledger_product_id=None, ledger_source="direct_handout"), {31: "Asha"}, {})
    assert row["product_id"] is None
    assert LedgerRowSerializer(row).data["product_id"] is None


def test_incident_saved_views_follow_the_incident_readers():
    assert ENTITY_ACTIONS["incidents"] == READER_ACTIONS
    # Handover-desk actions alone never open the register (217c / 224(d)).
    assert rbac.Action.ISSUE_REQUEST not in ENTITY_ACTIONS["incidents"]

