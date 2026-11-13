"""Scheduler admission is inert by default and classifies unavailable configuration."""
import pytest
from django.db import connection, transaction

from apps.audit.batch_scheduler import is_writable_primary, run_audit_attestation
from apps.audit.models import AuditSigningKey


@pytest.mark.django_db
def test_unconfigured_scheduler_performs_no_database_work(settings, django_assert_num_queries):
    settings.AUDIT_ATTESTATION_ANCHOR_BACKEND = ""
    with django_assert_num_queries(0):
        assert run_audit_attestation() is None


@pytest.mark.django_db(transaction=True)
def test_read_only_transaction_is_refused_before_sink_creation(settings):
    settings.AUDIT_ATTESTATION_ANCHOR_BACKEND = "invalid-backend"
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
        assert is_writable_primary() is False
        assert run_audit_attestation() == {"sealed": 0, "failed": 0, "skipped": "non_writable_primary"}


@pytest.mark.django_db
def test_invalid_configured_sink_is_one_failure_without_activating_a_signer(settings, caplog):
    settings.AUDIT_ATTESTATION_ANCHOR_BACKEND = "invalid-backend"
    before = AuditSigningKey.objects.count()
    assert run_audit_attestation() == {"sealed": 0, "failed": 1}
    assert AuditSigningKey.objects.count() == before
    assert "audit_attestation_sink_unavailable" in caplog.text


@pytest.mark.django_db(transaction=True)
def test_scheduler_seals_all_provisioned_scopes_once_through_the_real_http_sink(settings, monkeypatch):
    import requests
    from apps.audit.anchors_http import HttpCollectorAnchorSink
    from apps.audit.batches import activate_scope
    from apps.audit.models import AuditBatch, AuditMacKey
    from apps.audit.services import record
    from apps.makerspaces.models import Makerspace
    from tests.audit_batch_helpers import MemoryAnchorSink

    settings.AUDIT_ATTESTATION_DEPLOYMENT_ID = "cx6-scheduler-deployment"
    settings.AUDIT_ATTESTATION_ANCHOR_BACKEND = "http"
    settings.AUDIT_ATTESTATION_HTTP_URL = "https://scheduler-collector.test/anchors"
    settings.AUDIT_ATTESTATION_HTTP_BEARER_TOKEN = "scheduler-token"
    first = Makerspace.objects.create(name="Scheduler first", slug="cx6-scheduler-first")
    second = Makerspace.objects.create(name="Scheduler second", slug="cx6-scheduler-second")
    collector = MemoryAnchorSink()

    class Answer:
        def __init__(self, value):
            self.value = value
            self.status_code = 404 if value is None else 200

        def json(self):
            return self.value

    def get(url, *, params, **kwargs):
        if params.get("entry_type") == "scope_head":
            seq, signer, root = collector.fetch_scope_head(params["deployment_id"], params["scope"])
            return Answer({"batch_seq": seq, "signer_fingerprint": signer, "merkle_root": root.hex()})
        if params.get("entry_type") == "key_rotation":
            return Answer(collector.fetch_rotation((params["deployment_id"], params["scope"],
                params["old_fingerprint"], params["new_fingerprint"], params["last_old_batch_seq"])))
        return Answer(collector.fetch((params["deployment_id"], params["scope"],
                                       params["signer_fingerprint"], params["batch_seq"])))

    monkeypatch.setattr(requests, "get", get)
    monkeypatch.setattr(requests, "post", lambda url, *, json, **kwargs: Answer(collector.publish(json)))
    sink = HttpCollectorAnchorSink()
    scopes = list(AuditMacKey.objects.values_list("makerspace_id", flat=True))
    assert {first.pk, second.pk} <= set(scopes)
    for identifier in scopes:
        activate_scope(identifier, sink)
        maker = Makerspace.objects.get(pk=identifier) if identifier is not None else None
        record(None, "cx6.scheduler.row", makerspace=maker)
    assert run_audit_attestation() == {"sealed": len(scopes), "failed": 0}
    assert AuditBatch.objects.count() == len(scopes)
    assert run_audit_attestation() == {"sealed": 0, "failed": 0}
    assert AuditBatch.objects.count() == len(scopes)
