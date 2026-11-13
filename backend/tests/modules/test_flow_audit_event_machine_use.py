"""Flow audit (decision 342, 214-218): machine use logged against an event, across Machines and Events.

Journey: a participant runs a machine session for an event; staff tag it; the event is cancelled or a
module is switched off and on again. The link is history: it survives, nothing is re-created or
double-audited, the per-event report follows BOTH modules, and a cancelled or foreign event is never
offered for new use.
"""
import pytest
from rest_framework.exceptions import ValidationError

from apps.events import machine_use_services as services
from apps.events.machine_use_summary import rows_for
from apps.events.models import Event
from apps.events.models_machine_use import MachineEventLink
from apps.machines import event_use
from apps.makerspaces.guards import SurfaceOff
from apps.operations.reports_machine_event import build_machine_use_by_event
from tests.events.test_machine_use_342 import actions, finish, new_session, register, world
from tests.module_helpers import disable_module

pytestmark = pytest.mark.django_db(transaction=True)


def _enable(space, module):
    space.refresh_from_db()
    space.enabled_modules = sorted(set(space.enabled_modules) | {module})
    space.save(update_fields=["enabled_modules"])


def _linked_finished_session(slug, minutes=40):
    w = world(slug)
    session = new_session(w)
    services.manage(w.staff, session, w.event.pk)
    finish(session, minutes)
    return w, session


def test_cancelling_the_event_keeps_the_link_and_the_minutes_but_offers_it_to_nobody_new():
    w, _session = _linked_finished_session("fa-mu-cancel")
    Event.objects.filter(pk=w.event.pk).update(status=Event.Status.CANCELLED)
    event = Event.objects.get(pk=w.event.pk)
    assert MachineEventLink.objects.filter(event=event).count() == 1
    assert [(r["kind"], r["minutes"]) for r in rows_for(event)] == [("session", 40)]
    # A new session by a registered participant cannot be tagged to the cancelled event.
    register(event, w.member)
    with pytest.raises(ValidationError) as caught:
        event_use.attach(new_session(w), event.pk, actor=w.member)
    assert caught.value.detail["code"] == "event_not_eligible"
    assert MachineEventLink.objects.filter(event=event).count() == 1


def test_per_event_report_needs_both_modules_and_comes_back_with_them_with_data_kept():
    w, _session = _linked_finished_session("fa-mu-report")
    count = lambda: sum(r["sessions"] for r in build_machine_use_by_event(w.space.pk, actor=w.staff).records)  # noqa: E731
    assert count() == 1
    for module in ("events", "machines"):
        disable_module(w.space, module)
        with pytest.raises(SurfaceOff) as off:
            count()
        assert module in str(off.value), f"{module} off must refuse the cross-module report"
        assert MachineEventLink.objects.count() == 1  # retained, only hidden
        _enable(w.space, module)
        assert count() == 1, f"{module} back on restores the rows without any replay"
    assert actions("machine_event.linked").count() == 1  # the switches wrote no extra link audit


def test_tagging_is_refused_with_events_off_then_works_when_it_is_back_on():
    w = world("fa-mu-switch")
    register(w.event, w.member)
    disable_module(w.space, "events")
    session = new_session(w)
    with pytest.raises(ValidationError) as caught:
        event_use.attach(session, w.event.pk, actor=w.member)
    assert caught.value.detail["code"] == "events_off"
    assert not MachineEventLink.objects.exists()
    _enable(w.space, "events")
    session = type(session).objects.get(pk=session.pk)  # fresh row: no cached makerspace with the module off
    link = event_use.attach(session, w.event.pk, actor=w.member)
    assert link.event_id == w.event.pk
    assert actions("machine_event.linked").count() == 1


def test_setting_the_same_event_twice_is_a_no_op_with_one_link_and_one_audit_row():
    w = world("fa-mu-idem")
    session = new_session(w)
    first = services.manage(w.staff, session, w.event.pk)
    again = services.manage(w.staff, session, w.event.pk)
    assert first.pk == again.pk
    assert MachineEventLink.objects.count() == 1
    assert actions("machine_event.linked").count() == 1
    assert not actions("machine_event.changed").exists()


def test_another_spaces_event_cannot_be_linked_and_its_existence_is_not_revealed():
    w = world("fa-mu-tenant")
    foreign = world("fa-mu-tenant-other").event
    session = new_session(w)
    with pytest.raises(ValidationError) as caught:
        services.manage(w.staff, session, foreign.pk)
    assert caught.value.detail["code"] == "event_not_linkable"
    with pytest.raises(ValidationError) as unknown:
        services.manage(w.staff, session, 10**9)
    assert unknown.value.detail["code"] == caught.value.detail["code"]  # same answer: no oracle
    assert not MachineEventLink.objects.exists()
