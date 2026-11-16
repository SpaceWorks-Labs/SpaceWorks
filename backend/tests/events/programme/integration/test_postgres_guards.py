from uuid import uuid4

import pytest
from django.db import DatabaseError, transaction

from apps.events.models_commands import EventCommandReceipt
from apps.events.judging.models_definitions import JudgingRound, JudgingCriterion
from tests.events.staff_grant_helpers import grant_fixture

pytestmark = pytest.mark.django_db


def test_admission_receipt_completes_once_but_cannot_be_rewritten():
    _, manager, _, event, _ = grant_fixture()
    row = EventCommandReceipt.objects.create(event=event, actor=manager,
        operation_uuid=uuid4(), request_sha256="a" * 64, response_reference=None)
    row.response_reference = {"kind": "application", "id": 1}
    row.save(update_fields=("response_reference",))
    with pytest.raises(DatabaseError), transaction.atomic():
        EventCommandReceipt.objects.filter(pk=row.pk).update(response_reference={"id": 2})
    with pytest.raises(DatabaseError), transaction.atomic():
        EventCommandReceipt.objects.filter(pk=row.pk).update(request_sha256="b" * 64)


def test_opened_round_and_criteria_reject_raw_updates():
    _, _, _, event, _ = grant_fixture()
    round = JudgingRound.objects.create(event=event, key="round", mode="weighted_1_5")
    criterion = JudgingCriterion.objects.create(round=round, key="impact", label="Impact",
        weight=1, anchors={})
    round.state, round.configuration = "open", {"criteria": [{"key": "impact"}]}
    round.save()
    with pytest.raises(DatabaseError), transaction.atomic():
        JudgingRound.objects.filter(pk=round.pk).update(min_reviews=10)
    with pytest.raises(DatabaseError), transaction.atomic():
        JudgingCriterion.objects.filter(pk=criterion.pk).update(weight=2)


def test_cross_event_definition_reference_is_rejected_by_database():
    from apps.events.judging.models_definitions import HackathonTrack, HackathonPrize
    from tests.events.ticketing_helpers import open_event
    space, _, _, first, _ = grant_fixture()
    second = open_event(space)
    track = HackathonTrack.objects.create(event=first, name="Hardware")
    with pytest.raises(DatabaseError), transaction.atomic():
        HackathonPrize.objects.create(event=second, track=track, name="Spliced prize")
