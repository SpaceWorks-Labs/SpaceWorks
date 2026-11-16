"""Decision creator subject export excludes private association and CAS data."""
from datetime import timedelta
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.data_export.datasets import DATASETS
from apps.data_export.subject_archive import project_subject_row
from apps.data_export.subject_selectors import subject_query
from apps.data_export.types import Fidelity
from apps.events.models import Event
from apps.events.models_booking_decision import EventBookingDecision
from tests.events.orders_helpers import l6_space, make_staff

pytestmark = pytest.mark.django_db


def test_creator_subject_projection_omits_event_booking_and_intent():
    maker = l6_space("decision-subject")
    actor, other = make_staff(maker, "decision-subject-actor"), make_staff(maker, "decision-subject-other")
    start = timezone.now() + timedelta(days=1)
    event = Event.objects.create(makerspace=maker, title="Private Event", starts_at=start,
                                 ends_at=start + timedelta(hours=1), registration_audience="accounts", status="draft")
    row = EventBookingDecision.objects.create(makerspace=maker, event=event, creator=actor,
                                               operation_id=uuid4(), intent={"secret": "private-sentinel"})
    assert subject_query(EventBookingDecision, actor, maker.pk).filter(pk=row.pk).exists()
    assert not subject_query(EventBookingDecision, other, maker.pk).filter(pk=row.pk).exists()
    dataset = DATASETS[(Fidelity.PORTABLE, "events/booking_decisions.csv")]
    projected = project_subject_row(dataset, row, actor.pk)
    assert not {"event", "booking", "intent", "operation_id", "generation", "revision"} & set(projected)
    assert "private-sentinel" not in str(projected)
