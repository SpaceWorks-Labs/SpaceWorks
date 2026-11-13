"""Venue debt must never silently disappear at portable-import materialization."""
import pytest

from apps.tenant_migration.insertion_errors import VenueFeeDebtProvenanceUnavailable
from apps.tenant_migration.venue_fee_import_preflight import refuse_orphan_venue_payments
from apps.tenant_migration.views_common import protocol_error

pytestmark = pytest.mark.django_db(transaction=True)


class Archive:
    def __init__(self, payments, provenance=(), external=()):
        self.payments = payments
        self.sidecars = {"migration/reference_provenance.jsonl": provenance,
                         "migration/external_references.jsonl": external}

    def raw_rows(self, label):
        assert label == "payments.Payment"
        yield from self.payments

    def json_lines(self, path):
        yield from self.sidecars[path]


def marker(pk, *, reported_type="event_venue_fee"):
    return {"source_model_label": "payments.Payment", "source_object_id": str(pk),
            "field_name": "subject_id", "kind": "orphaned_payment_subject",
            "detail": {"subject_type": reported_type}}


@pytest.mark.parametrize("sidecar", ["provenance", "external"])
def test_venue_orphan_is_refused_with_precise_non_sensitive_code(sidecar):
    archive = Archive([{"id": "41", "subject_type": "event_venue_fee"}], **{sidecar: [marker(41)]})
    with pytest.raises(VenueFeeDebtProvenanceUnavailable) as caught:
        refuse_orphan_venue_payments(archive)
    response = protocol_error(caught.value)
    assert response.status_code == 409
    assert response.data["code"] == "venue_fee_payment_provenance_unavailable"
    assert "41" not in response.data["detail"]


def test_actual_payment_type_overrides_untrusted_sidecar_and_other_types_are_unchanged():
    payments = [{"id": "1", "subject_type": "booking"}, {"id": "2", "subject_type": "event_venue_fee"}]
    refuse_orphan_venue_payments(Archive(payments, [marker(1)]))
    with pytest.raises(VenueFeeDebtProvenanceUnavailable):
        refuse_orphan_venue_payments(Archive(payments, [marker(2, reported_type="booking")]))
    refuse_orphan_venue_payments(Archive(payments))  # retained venue fee is not an orphan


def test_check_continues_after_a_full_batch():
    references = [marker(i, reported_type="booking") for i in range(1, 502)]
    payments = [{"id": str(i), "subject_type": "booking"} for i in range(1, 501)]
    payments.append({"id": "501", "subject_type": "event_venue_fee"})
    with pytest.raises(VenueFeeDebtProvenanceUnavailable):
        refuse_orphan_venue_payments(Archive(payments, references))


def test_refusal_happens_before_object_preparation_or_target_creation(monkeypatch):
    from types import SimpleNamespace
    from apps.tenant_migration import materialization

    archive = Archive([{"id": "9", "subject_type": "event_venue_fee"}], [marker(9)])
    monkeypatch.setattr(materialization, "PortableArchive", lambda _: archive)
    stages, cleanup = [], []
    monkeypatch.setattr(materialization, "prepare_import_objects", lambda *_: stages.append("objects"))
    monkeypatch.setattr(materialization, "create_target_makerspace", lambda *_args, **_kwargs: stages.append("target"))
    monkeypatch.setattr(materialization, "handle_materialization_failure", lambda **kw: cleanup.append(kw["error"]))
    with pytest.raises(VenueFeeDebtProvenanceUnavailable):
        materialization.materialize_tenant("unused", SimpleNamespace(pk=1), ())
    assert stages == [] and len(cleanup) == 1


def test_preflight_temp_index_is_removed_inside_an_outer_transaction():
    from django.db import transaction
    from apps.tenant_migration.reference_state import ReferenceState, TABLE_NAME
    from django.db import connection

    good = Archive([{"id": "2", "subject_type": "event_venue_fee"}])
    bad = Archive([{"id": "9", "subject_type": "event_venue_fee"}], [marker(9)])
    with transaction.atomic():
        with pytest.raises(VenueFeeDebtProvenanceUnavailable):
            refuse_orphan_venue_payments(bad)
        refuse_orphan_venue_payments(good)
        # The actual importer may create its ReferenceState in the same transaction.
        state = ReferenceState(good)
        assert not state.has_any("payments.Payment", ["2"], "subject_id")
        with connection.cursor() as cursor:
            cursor.execute(f"DROP TABLE {TABLE_NAME}")


def test_preexisting_import_index_is_not_dropped_on_name_collision():
    from django.db import DatabaseError, connection, transaction
    from apps.tenant_migration.reference_state import ReferenceState, TABLE_NAME

    existing = Archive([{"id": "8", "subject_type": "booking"}], [marker(8)])
    with transaction.atomic():
        state = ReferenceState(existing)
        with pytest.raises(DatabaseError):
            refuse_orphan_venue_payments(Archive([]))
        assert state.has_any("payments.Payment", ["8"], "subject_id")
        with connection.cursor() as cursor:
            cursor.execute(f"DROP TABLE {TABLE_NAME}")
