"""Decision 296 addendum: an organiser plans ANY number of submission stages (1..50 technical ceiling).

The per-space ``hackathon_stages`` limit (decision 284; unset = no limit) can only lower the ceiling and
refuses only ADDING stages; an event above a lowered limit keeps and edits its plan.
"""
from datetime import timedelta
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.events.submissions import stage_service
from apps.events.submissions.errors import SubmissionError
from apps.events.submissions.models_stages import MAX_STAGES, SubmissionStage
from apps.events.submissions.stage_projection import editor_options
from apps.events.submissions.stage_service import fingerprint
from apps.managed_hosting.extra_quota_counters import COUNTERS
from apps.managed_hosting.extra_quotas import ExtraQuotaReached, SPECS
from apps.makerspaces.limit_registry import AREA_OF, ENFORCEMENT
from apps.makerspaces.limits_core import EXTRA_QUOTA_LIMIT_KEYS
from tests.events.collab_helpers import make_staff
from tests.submit_content_local.stage_helpers import world

pytestmark = pytest.mark.django_db


@pytest.fixture
def w(monkeypatch):
    row = world(monkeypatch, teams=1)
    row.manager = make_staff(row.event.makerspace, username=f"stage-count-{uuid4().hex[:6]}")
    return row


def plan(w, count):
    """``count`` valid stages, deadlines one hour apart, all before the event ends."""
    start = timezone.now() + timedelta(hours=1)
    return [{"name": f"Stage {i + 1}", "deadline": start + timedelta(hours=i)} for i in range(count)]


def replace(w, stages):
    current = list(SubmissionStage.objects.filter(event=w.event).order_by("position"))
    return stage_service.replace(actor=w.manager, event_id=w.event.pk, data={
        "operation_id": uuid4(), "expected_fingerprint": fingerprint(current), "preset": "", "stages": stages})


def limit(w, value):
    space = w.event.makerspace
    space.resource_limit_overrides = {**(space.resource_limit_overrides or {}), "hackathon_stages": value}
    space.save(update_fields=["resource_limit_overrides"])


@pytest.mark.parametrize("count", [1, 3, 12, MAX_STAGES])
def test_any_number_of_stages_up_to_the_ceiling_is_saved_in_order(w, count):
    result = replace(w, plan(w, count))
    assert [s["position"] for s in result["stages"]] == list(range(1, count + 1))
    assert SubmissionStage.objects.filter(event=w.event).count() == count


def test_the_ceiling_is_fifty_and_more_is_refused():
    from apps.events.submissions.stage_rules import check_plan
    from types import SimpleNamespace
    event = SimpleNamespace(ends_at=timezone.now() + timedelta(days=30))
    stages = [{"name": f"S{i}", "deadline": timezone.now() + timedelta(hours=i + 1)} for i in range(MAX_STAGES + 1)]
    with pytest.raises(SubmissionError) as caught:
        check_plan(event, stages)
    assert MAX_STAGES == 50 and caught.value.detail["code"] == "invalid_stage_count"


def test_unset_limit_reports_the_ceiling_and_a_set_limit_lowers_it(w):
    assert editor_options(w.event)["max_stages"] == MAX_STAGES
    limit(w, 3)
    w.event.makerspace.refresh_from_db()
    assert editor_options(w.event)["max_stages"] == 3
    limit(w, 500)
    w.event.makerspace.refresh_from_db()
    assert editor_options(w.event)["max_stages"] == MAX_STAGES


def test_a_set_limit_refuses_adding_past_it_but_keeps_an_existing_larger_plan(w):
    replace(w, plan(w, 5))
    limit(w, 3)
    with pytest.raises(ExtraQuotaReached) as caught:
        replace(w, plan(w, 6))
    assert caught.value.code == "hackathon_stages_quota_reached"
    stored = list(SubmissionStage.objects.filter(event=w.event).order_by("position"))
    # Editing (same count) and shrinking an over-limit plan both still work.
    same = [{"id": s.pk, "name": f"{s.name}!", "deadline": s.deadline} for s in stored]
    assert len(replace(w, same)["stages"]) == 5
    assert len(replace(w, same[:4])["stages"]) == 4


def test_the_key_is_registered_everywhere_a_limit_key_must_be(w):
    assert "hackathon_stages" in EXTRA_QUOTA_LIMIT_KEYS and "hackathon_stages" in SPECS
    assert AREA_OF["hackathon_stages"] == "events" and "hackathon_stages" in ENFORCEMENT
    replace(w, plan(w, 3))
    assert COUNTERS["hackathon_stages"](w.event.makerspace) == 3
