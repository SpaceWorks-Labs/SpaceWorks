"""AN-c1: L21a application stages as event-funnel steps (counts only)."""
import pytest

from apps.events.hackathons import admission_stage_funnel
from apps.events.hackathons.admission_stage_models import AdmissionStage, AdmissionStageEntry
from apps.events.programme.analytics_serializers import FunnelSerializer
from apps.operations.reports_events_programme import project_funnel
from tests.events.programme.admission.test_support import submitted, world  # noqa: F401
from tests.events.ticketing_helpers import account

pytestmark = pytest.mark.django_db


@pytest.fixture
def staged(world, monkeypatch):  # noqa: F811
    monkeypatch.setattr(admission_stage_funnel, "feature_enabled", lambda *args: True)
    return world


def stage(world, position, name, state="open"):
    return AdmissionStage.objects.create(event=world.event, position=position, name=name, state=state)


def enter(world, application, stage_row, kind="entered"):
    return AdmissionStageEntry.objects.create(event=world.event, application=application, stage=stage_row, kind=kind)


def test_stage_counts_follow_furthest_entry_and_skip_drafts(staged):
    first, second, third = stage(staged, 1, "Screening"), stage(staged, 2, "Interview"), stage(staged, 3, "Panel")
    stage(staged, 4, "Draft round", state="draft")
    apps_ = [submitted(staged, account(f"funnel-{index}")) for index in range(4)]
    enter(staged, apps_[0], first)                 # implicit first stage made explicit
    enter(staged, apps_[1], second)
    enter(staged, apps_[2], second)
    enter(staged, apps_[2], third)
    enter(staged, apps_[3], second, kind="left")   # left at stage 2: it still reached it
    rows = admission_stage_funnel.stage_counts(staged.event)
    assert rows == [{"position": 1, "name": "Screening", "count": 4},
                    {"position": 2, "name": "Interview", "count": 3},
                    {"position": 3, "name": "Panel", "count": 1}]


def test_no_stages_without_the_switch_config_or_stages(world, monkeypatch):  # noqa: F811
    assert admission_stage_funnel.stage_counts(world.event) == []  # switch off
    monkeypatch.setattr(admission_stage_funnel, "feature_enabled", lambda *args: True)
    assert admission_stage_funnel.stage_counts(world.event) == []  # no stages yet
    stage(world, 1, "Only draft", state="draft")
    assert admission_stage_funnel.stage_counts(world.event) == []
    world.config.enabled = False
    world.config.save(update_fields=["enabled"])
    stage(world, 2, "Open", state="open")
    assert admission_stage_funnel.stage_counts(world.event) == []


def test_project_funnel_places_stages_between_responded_and_going(staged):
    first, second = stage(staged, 1, "Screening"), stage(staged, 2, "Interview")
    applications = [submitted(staged, account(f"funnel-p-{index}")) for index in range(3)]
    enter(staged, applications[0], second)
    funnel = project_funnel(staged.event)
    keys = [row["key"] for row in funnel["stages"]]
    assert keys == ["responded", "application_stage", "application_stage", "going", "checked_in", "feedback"]
    screening, interview = funnel["stages"][1], funnel["stages"][2]
    assert (screening["label"], screening["count"], screening["stage_position"]) == ("Screening", 3, 1)
    assert (interview["count"], interview["denominator"], interview["stage_position"]) == (1, 3, 2)
    assert funnel["stages"][3]["denominator"] == 1  # going is measured against the last stage
    assert all(row["stage_position"] is None for row in funnel["stages"] if row["key"] != "application_stage")
    serializer = FunnelSerializer(data={**funnel, "generated_at": funnel["generated_at"].isoformat()})
    assert serializer.is_valid(), serializer.errors
    assert "funnel-p-0" not in str(funnel)  # counts only


def test_funnel_without_stages_is_unchanged(world):  # noqa: F811
    funnel = project_funnel(world.event)
    assert [row["key"] for row in funnel["stages"]] == ["responded", "going", "checked_in", "feedback"]
    assert funnel["stages"][1]["denominator"] == funnel["stages"][0]["count"]
