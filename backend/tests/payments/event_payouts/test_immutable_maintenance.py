"""Mapper marking alone cannot authorize edits to immutable financial history."""
from types import SimpleNamespace
import pytest
from apps.payments.event_payouts.model_base import maintenance_fields
from apps.payments.event_payouts.payout_models import EventPayoutEntry, METHODS
from apps.event_reimbursements.award_models import GrantAwardRevision


def test_retained_payout_choices_are_self_contained():
    assert set(METHODS) == {"cash", "upi", "bank_transfer", "cheque", "other", "paypal", "wise"}
    row = EventPayoutEntry()
    row._state.adding = False
    with pytest.raises(RuntimeError, match="immutable"):
        row.save()


def test_ordinary_history_save_does_not_reach_database():
    row = GrantAwardRevision()
    row._state.adding = False
    with pytest.raises(RuntimeError, match="immutable"):
        row.save()


@pytest.mark.django_db
def test_spoofed_mapper_marker_still_requires_the_database_closed_operation(monkeypatch):
    import apps.payments.event_payouts.model_base as base
    row = SimpleNamespace(_pii_writing=True)
    monkeypatch.setattr(base, "fields_for", lambda instance: [SimpleNamespace(field_name="decision_summary")])
    monkeypatch.setattr(base, "makerspace_id_for", lambda instance, field: 99999999)
    with pytest.raises(RuntimeError, match="immutable"):
        maintenance_fields(row)
