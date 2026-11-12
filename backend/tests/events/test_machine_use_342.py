"""Decision 342 (+ addendum): machine use logged with an event. No switch; requester may tag; area manager manages.

Not run in source preparation (TEST-3 owns the stack): written against `session_world` and the event helpers.
"""
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.events import machine_use_costs, machine_use_services as services
from apps.events.machine_use_eligibility import eligible_events
from apps.events.machine_use_summary import rows_for, totals_for
from apps.events.models import Event, EventRegistration
from apps.events.models_machine_use import MachineEventCostApproval, MachineEventLink
from apps.machines import event_use, sessions_service as service
from apps.payments.models import Payment
from tests.machines.session_helpers import features, session_world
from tests.rbac_f6_helpers import community_member

pytestmark = pytest.mark.django_db(transaction=True)


def make_event(space, title="Maker faire", **extra):
    start = timezone.now() + timedelta(days=3)
    return Event.objects.create(makerspace=space, title=title, starts_at=start, ends_at=start + timedelta(hours=4),
                                status=extra.pop("status", Event.Status.PUBLISHED), **extra)


def register(event, user):
    return EventRegistration.objects.create(event=event, member=user, name=user.username, email=user.email,
                                            phone=user.phone or "1", status=EventRegistration.Status.REGISTERED)


def world(slug):
    w = session_world(slug)
    w.space.enabled_modules = sorted(set(w.space.enabled_modules) | {"events", "machines"})
    w.space.save(update_fields=["enabled_modules"])
    w.event = make_event(w.space)
    return w


def new_session(w):
    return service.start(w.machines[0], w.member, actor=w.member, source="member_qr")


def actions(name):
    return AuditLog.objects.filter(action=name)


def test_eligibility_is_registered_participants_in_this_space_and_open_events_only():
    w = world("mu-elig")
    other_space = world("mu-elig-other")
    register(w.event, w.member)
    cancelled = make_event(w.space, "Called off", status=Event.Status.CANCELLED)
    register(cancelled, w.member)
    stranger_event = make_event(w.space, "Not mine")
    foreign = make_event(other_space.space, "Elsewhere")
    ids = set(eligible_events(w.member, w.space).values_list("pk", flat=True))
    assert ids == {w.event.pk}
    assert stranger_event.pk not in ids and foreign.pk not in ids and cancelled.pk not in ids
    assert not eligible_events(None, w.space).exists()


def test_requester_tags_a_session_with_an_eligible_event_and_it_is_audited():
    w = world("mu-attach")
    register(w.event, w.member)
    session = new_session(w)
    link = event_use.attach(session, w.event.pk, actor=w.member)
    assert (link.event_id, link.source, link.session_id) == (w.event.pk, "requester", session.pk)
    meta = actions("machine_event.linked").get().meta
    assert meta["after_event_id"] == w.event.pk and meta["before_event_id"] is None


def test_requester_cannot_tag_an_event_they_may_not_act_for_or_one_in_another_space():
    w = world("mu-refuse")
    foreign = make_event(world("mu-refuse-other").space)
    session = new_session(w)
    for event in (w.event, foreign):
        with pytest.raises(ValidationError) as caught:
            event_use.attach(session, event.pk, actor=w.member)
        assert caught.value.detail["code"] == "event_not_eligible"
    assert not MachineEventLink.objects.exists()


def test_no_event_means_no_link_and_no_error():
    w = world("mu-none")
    assert event_use.attach(new_session(w), None, actor=w.member) is None


def test_events_module_off_refuses_a_named_event():
    w = world("mu-off")
    register(w.event, w.member)
    w.space.enabled_modules = sorted(set(w.space.enabled_modules) - {"events"})
    w.space.save(update_fields=["enabled_modules"])
    with pytest.raises(ValidationError) as caught:
        event_use.attach(new_session(w), w.event.pk, actor=w.member)
    assert caught.value.detail["code"] == "events_off"


def test_adapter_path_ignores_an_ineligible_event_and_never_raises():
    w = world("mu-adapter")
    session = new_session(w)
    assert event_use.attach_quiet(session, w.event.pk) is None  # member is not a participant
    assert event_use.attach_quiet(session, "not-a-number") is None
    register(w.event, w.member)
    assert event_use.attach_quiet(session, w.event.pk).source == "adapter"


def test_area_manager_sets_changes_and_clears_with_before_and_after_audit():
    w = world("mu-manage")
    other = make_event(w.space, "Second")
    session = new_session(w)
    link = services.manage(w.staff, session, w.event.pk)  # never offered to the member: manager may log it
    assert link.source == "manager"
    services.manage(w.staff, session, other.pk)
    assert services.manage(w.staff, session, None) is None
    assert not MachineEventLink.objects.exists()
    changed = actions("machine_event.changed").get().meta
    assert (changed["before_event_id"], changed["after_event_id"]) == (w.event.pk, other.pk)
    cleared = actions("machine_event.cleared").get().meta
    assert (cleared["before_event_id"], cleared["after_event_id"]) == (other.pk, None)


def test_a_plain_member_cannot_manage_and_a_foreign_event_is_not_linkable():
    w = world("mu-perm")
    session = new_session(w)
    from rest_framework.exceptions import NotFound
    with pytest.raises(NotFound):
        services.manage(w.member, session, w.event.pk)
    foreign = make_event(world("mu-perm-other").space)
    with pytest.raises(ValidationError) as caught:
        services.manage(w.staff, session, foreign.pk)
    assert caught.value.detail["code"] == "event_not_linkable"


def finish(session, minutes=30):
    return service.stop(session, actor=session.member, reason="member",
                        at=session.started_at + timedelta(minutes=minutes))


def test_cost_approval_is_a_record_only_and_locks_the_link_until_withdrawn():
    w = world("mu-cost")
    features(w.space, {"charges.events"})
    session = new_session(w)
    services.manage(w.staff, session, w.event.pk)
    finish(session)
    link = MachineEventLink.objects.get()
    charge = Payment.objects.get(subject_type="machine_session", subject_id=session.pk)
    before = (charge.amount, charge.status, charge.member_id)
    row = machine_use_costs.decide(w.staff, w.event, link.pk, "approved", "Faire budget")
    assert (row.amount, row.currency, row.payment_id) == (charge.amount, charge.currency, charge.pk)
    charge.refresh_from_db()
    assert (charge.amount, charge.status, charge.member_id) == before  # the member's own charge stands
    assert machine_use_costs.decide(w.staff, w.event, link.pk, "approved").pk == row.pk  # idempotent
    with pytest.raises(ValidationError) as caught:
        services.manage(w.staff, session, None)
    assert caught.value.detail["code"] == "cost_approved"
    machine_use_costs.decide(w.staff, w.event, link.pk, "withdrawn")
    assert services.manage(w.staff, session, None) is None
    assert actions("machine_event.cost_approved").count() == 1 and actions("machine_event.cost_withdrawn").count() == 1


def test_cost_approval_needs_event_finance_and_event_authority():
    w = world("mu-cost-off")
    session = new_session(w)
    services.manage(w.staff, session, w.event.pk)
    link = MachineEventLink.objects.get()
    with pytest.raises(ValidationError) as caught:
        machine_use_costs.decide(w.staff, w.event, link.pk, "approved")
    assert caught.value.detail["code"] == "event_finance_off"
    features(w.space, {"charges.events"})
    from rest_framework.exceptions import NotFound
    with pytest.raises(NotFound):
        machine_use_costs.decide(w.member, w.event, link.pk, "approved")
    assert not MachineEventCostApproval.objects.exists()


def test_event_summary_rows_and_totals_per_currency():
    w = world("mu-summary")
    session = new_session(w)
    services.manage(w.staff, session, w.event.pk)
    finish(session, 40)
    rows = rows_for(w.event)
    assert [(r["kind"], r["minutes"], r["person_id"]) for r in rows] == [("session", 40, w.member.pk)]
    totals = totals_for(rows)
    assert totals["sessions"] == 1 and totals["minutes"] == 40 and totals["approved_to_event"] == {}


def test_api_member_picker_lists_only_my_events_and_staff_route_sets_the_link():
    w = world("mu-api")
    register(w.event, w.member)
    make_event(w.space, "Not mine")
    client = APIClient()
    client.force_authenticate(w.member)
    listed = client.get(reverse("member-machine-use-events", kwargs={"makerspace_id": w.space.pk}))
    assert listed.status_code == 200 and [row["id"] for row in listed.data] == [w.event.pk]
    session = new_session(w)
    url = reverse("admin-machine-use-event", kwargs={"makerspace_id": w.space.pk, "kind": "session", "pk": session.pk})
    assert client.put(url, {"event_id": w.event.pk}, format="json").status_code == 404  # a member is not a manager
    client.force_authenticate(w.staff)
    done = client.put(url, {"event_id": w.event.pk}, format="json")
    assert done.status_code == 200 and done.data["event"]["id"] == w.event.pk
    cleared = client.put(url, {"event_id": None}, format="json")
    assert cleared.status_code == 200 and cleared.data["event"] is None


def test_a_member_sees_only_their_own_link_on_their_session():
    w = world("mu-privacy")
    session = new_session(w)
    services.manage(w.staff, session, w.event.pk)
    mine = event_use.event_summary(session)
    assert mine == {"id": w.event.pk, "title": w.event.title}
    other = community_member(w.space, "other")
    from apps.machines.models import MachineSession
    assert not MachineSession.objects.filter(member=other.user, event_link__isnull=False).exists()
