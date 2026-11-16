"""Subject export redacts optional-domain and operational identifiers."""
from datetime import timedelta
import pytest
from django.utils import timezone
from apps.data_export.datasets import DATASETS
from apps.data_export.subject_archive import project_subject_row
from apps.data_export.types import Fidelity
from apps.events.models import Event
from apps.events.models_loan_context import EventLoanContext
from tests.test_request_workflow import make_space, make_product, make_hardware_request

pytestmark = pytest.mark.django_db


def test_borrower_subject_projection_hides_private_event_and_revision():
    space = make_space("context-subject")
    request = make_hardware_request(space, make_product(space))
    start = timezone.now() + timedelta(days=1)
    event = Event.objects.create(makerspace=space, title="Private subject sentinel", starts_at=start, ends_at=start + timedelta(hours=1))
    row = EventLoanContext.objects.create(makerspace=space, request=request, event=event, active=True)
    dataset = DATASETS[(Fidelity.PORTABLE, "events/loan_contexts.csv")]
    projected = project_subject_row(dataset, row, request.requester_id)
    assert "event_id" not in projected and "event" not in projected
    assert "participant_registration_id" not in projected and "participant_registration" not in projected
    assert "revision" not in projected and "Private subject sentinel" not in str(projected)
