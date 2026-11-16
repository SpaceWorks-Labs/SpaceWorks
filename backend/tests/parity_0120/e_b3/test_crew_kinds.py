"""E-B3 crew kinds, staff edit, reorder and hide, and the kind filter behind its switch."""
import pytest

from apps.events.contributions import crew_reads, crew_workflow
from apps.events.hackathons.admission_errors import ProgrammeError
from apps.events.models import EventCrewMember
from tests.events.collab_helpers import make_event, make_member, make_space, make_staff

pytestmark = pytest.mark.django_db


def world(slug, *features):
    space = make_space(slug)
    space.enabled_features = [*features]
    space.save(update_fields=["enabled_features"])
    event = make_event(space, is_public=True)
    return space, event, make_staff(space)


def test_kind_requires_the_switch_and_shows_in_the_chip():
    space, event, staff = world("kinds-a", "events.crew")
    member = make_member(space, "kinds-m")
    with pytest.raises(ProgrammeError):
        crew_workflow.add(event, actor=staff, member=member, crew_role="Door", kind="judge")
    space.enabled_features = ["events.crew", "events.crew_kinds"]
    space.save(update_fields=["enabled_features"])
    crew = crew_workflow.add(event, actor=staff, member=member, crew_role="Door", kind="judge")
    assert crew.kind == "judge"
    chips = crew_reads.crew_labels(event, [crew.registration_id])
    assert chips[crew.registration_id].endswith("Door") and "·" in chips[crew.registration_id]
    assert crew_reads.crew_kinds(event, [crew.registration_id]) == {crew.registration_id: "judge"}
    assert crew_reads.crew_kind_for(event, crew.registration_id) == "judge"


def test_kind_filter_and_labels_are_inert_while_the_switch_is_off():
    space, event, staff = world("kinds-b", "events.crew", "events.crew_kinds")
    first, second = make_member(space, "kinds-1"), make_member(space, "kinds-2")
    one = crew_workflow.add(event, actor=staff, member=first, kind="mentor")
    crew_workflow.add(event, actor=staff, member=second, kind="judge")
    assert [row.pk for row in crew_reads.roster(event, kind="mentor")] == [one.pk]
    space.enabled_features = ["events.crew"]
    space.save(update_fields=["enabled_features"])
    assert len(crew_reads.roster(event, kind="mentor")) == 2
    assert crew_reads.crew_kinds(event, [one.registration_id]) == {}
    assert crew_reads.crew_labels(event, [one.registration_id])[one.registration_id] == "Crew"


def test_staff_update_reorder_and_hide():
    space, event, staff = world("kinds-c", "events.crew", "events.crew_kinds")
    rows = [crew_workflow.add(event, actor=staff, member=make_member(space, f"kinds-r{i}")) for i in range(3)]
    updated = crew_workflow.update(event, actor=staff, crew_id=rows[0].pk, expected_version=rows[0].version,
                                   kind="organiser", staff_hidden=True)
    assert updated.kind == "organiser" and updated.staff_hidden and updated.version == rows[0].version + 1
    with pytest.raises(ProgrammeError):
        crew_workflow.update(event, actor=staff, crew_id=rows[0].pk, expected_version=rows[0].version, crew_role="x")
    crew_workflow.reorder(event, actor=staff, ids=[rows[2].pk, rows[0].pk, rows[1].pk])
    ordered = [row.pk for row in crew_reads.roster(event)]
    assert ordered == [rows[2].pk, rows[0].pk, rows[1].pk]
    with pytest.raises(ProgrammeError):
        crew_workflow.reorder(event, actor=staff, ids=[rows[0].pk, rows[0].pk, rows[1].pk])
    assert EventCrewMember.objects.get(pk=rows[0].pk).position == 2
