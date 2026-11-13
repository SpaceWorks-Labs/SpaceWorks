from datetime import timedelta
from uuid import uuid4
from unittest.mock import Mock

import pytest
from django.db import connection
from django.utils import timezone

from apps.events.certificates import print_cleanup
from apps.events.certificates.print_models import BadgePrintJob, EventBadgeTemplateRevision
from tests.events.programme.uploads.test_retained_recovery import normal, freeze
from tests.events.ticketing_helpers import event_space, open_event

pytestmark = pytest.mark.django_db(transaction=True)


def test_expired_print_cleanup_survives_module_disable_and_migrated_source_without_workflow_bypass(monkeypatch):
    normal()
    event = open_event(event_space("retained-print-cleanup"))
    revision = EventBadgeTemplateRevision.objects.create(event=event, document={}, stock="cr80-landscape")
    job = BadgePrintJob.objects.create(event=event, operation_id=uuid4(), request_sha256="a" * 64,
        fields_sha256="b" * 64, template={}, template_revision=revision, stock=revision.stock,
        registration_ids=[], object_key="print/retained-test", size_bytes=40,
        expires_at=timezone.now()-timedelta(minutes=1))
    event.makerspace.enabled_modules = []
    event.makerspace.save(update_fields=["enabled_modules"])
    freeze(event.makerspace)
    calls = []
    def delete(key):
        assert not connection.in_atomic_block
        calls.append(key)
    free = Mock()
    monkeypatch.setattr(print_cleanup.print_storage, "delete", delete)
    monkeypatch.setattr(print_cleanup.limits, "free_storage", free)
    assert print_cleanup.cleanup_job(job.pk)
    assert print_cleanup.cleanup_job(job.pk)
    assert calls == [job.object_key, job.object_key]
    assert free.call_count == 1
    job.refresh_from_db()
    assert job.state == "cancelled" and job.cleaned_at and job.next_cleanup_at
