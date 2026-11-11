"""Encrypted export accessors must not lazily fetch tenant relationships per row."""

import json

import pytest
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext

from apps.encryption.crypto import is_envelope
from apps.events.models import Event, EventFeedbackResponse, EventFeedbackSurvey, EventRegistration
from apps.operations.reports_event_exports import build_feedback, build_registrations
from tests.encryption.conftest import enabled_encryption
from tests.events.ticketing_helpers import event_space, open_event

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("kind", ["registrations", "feedback"])
@pytest.mark.parametrize("limit", [None, 24])
def test_encrypted_exports_eager_load_tenant_paths_with_constant_domain_queries(kind, limit):
    with enabled_encryption():
        space = event_space("encrypted-export")
        event = open_event(space)
        survey = EventFeedbackSurvey.objects.create(event=event, title="Feedback", questions=[{"id": "q", "label": "Feedback", "type": "short_text", "options": [], "required": False}])
        builder = build_registrations if kind == "registrations" else build_feedback
        model = EventRegistration if kind == "registrations" else EventFeedbackResponse
        field = "name" if kind == "registrations" else "answers_snapshot"
        expected = []
        query_counts = []
        for index in range(24):
            if kind == "registrations":
                row = model.objects.create(
                    event=event, name=f"Attendee {index}", email=f"attendee-{index}@example.test",
                    phone="1234567890", custom_answers={"question": f"Answer {index}"},
                )
                expected.append((row.pk, f"Attendee {index}", f"attendee-{index}@example.test"))
            else:
                row = model.objects.create(survey=survey, answers_snapshot=json.dumps({"answer": f"Answer {index}"}))
                expected.append((row.pk, {"answer": f"Answer {index}"}))
            assert is_envelope(model.objects.filter(pk=row.pk).values_list(field, flat=True).get())
            if index not in (0, 23):
                continue
            with override_settings(PII_ENCRYPTION_DUAL_READ=False), CaptureQueriesContext(connection) as queries:
                result = builder(space.pk, subject_kind="event", subject_id=event.pk, limit=limit)
            if kind == "registrations":
                actual = [(r["registration_id"], r["name"], r["email"]) for r in result.records]
                assert all(r["phone"] == "1234567890" for r in result.records)
            else:
                actual = [(r["response_id"], json.loads(r["answers"])) for r in result.records]
            assert actual == expected
            # DEK lookups are a separate encryption concern. Count domain reads,
            # including any accidental lazy event/survey lookups, without mocking crypto.
            tables = (model._meta.db_table, Event._meta.db_table, EventFeedbackSurvey._meta.db_table)
            domain_queries = [q["sql"] for q in queries if any(f'FROM "{table}"' in q["sql"] for table in tables)]
            query_counts.append(len(domain_queries))
            assert not any(f'FROM "{Event._meta.db_table}"' in q["sql"] for q in queries)
            assert not any(f'FROM "{EventFeedbackSurvey._meta.db_table}"' in q["sql"] for q in queries)
        assert query_counts == [1, 1]
        # The eager joins preserve the host predicate on both builder paths.
        foreign = event_space("foreign-export")
        assert not builder(foreign.pk, subject_kind="event", subject_id=event.pk).records
