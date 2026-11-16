"""Event-bound machine operations: named-event gates and the supervised registrant pool."""
import pytest
from django.utils import timezone

from apps.events.models_machine_use import MachineEventLink
from apps.machines.models import MachineServiceRequest, MachineSession, ServiceRequestFile, SupervisedSession
from apps.machines.service_storage import ServiceObjectValidationResult
from tests.events.checkin_helpers import register
from tests.machines.member_support_cx11b_g2 import member_world
from tests.machines.route_support_cx11b_g2 import command, prove
from tests.modules.switch_matrix_object_helpers import client_for

pytestmark = [pytest.mark.django_db, pytest.mark.area_machines, pytest.mark.area_machine_service]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("name", ["public-machine-job-submit", "member-machine-session-start",
                                "member-supervised-session-open", "member-supervised-people"])
def test_named_event_dependency_is_checked_before_any_creator_write_and_restores_links(native, name, monkeypatch):
    w = member_world(native)
    register(w.event, w.member)
    supervised = name.startswith("member-supervised")
    picker = name.endswith("people")
    if supervised:
        w.client = client_for(w.actor, w.space, native)
    body = {"event_id": w.event.pk}
    args = [w.machine.pk]
    if picker:
        w.bystander.display_name = "G2 Event attendee"
        w.bystander.save(update_fields=["display_name"])
        register(w.event, w.bystander)
        session = SupervisedSession.objects.create(makerspace=w.space, machine=w.machine, instructor=w.actor,
            opened_at=timezone.now(), event=w.event)
        args, body = [session.pk], {"q": "G2 Event attendee"}
    if name == "public-machine-job-submit":
        args = [w.space.slug]
        file = ServiceRequestFile.objects.create(makerspace=w.space, queue=w.queue, owner_user_id=w.member.pk,
            object_key=f"machine-service/{w.space.pk}/g2-event.svg", kind="model", original_filename="event.svg",
            content_type="image/svg+xml", file_policy_name="maker_formats")
        monkeypatch.setattr("apps.machines.job_files.validate_job_object", lambda file:
                            ServiceObjectValidationResult(size=13, content_type=file.content_type))
        body.update(queue_id=w.queue.pk, title="Event drawing", file_ids=[file.pk],
                    acknowledgements={"pickup_policy": True, "failure_policy": True, "own_content": True})

    def check(response):
        if picker:
            assert response.data == {"results": [{"id": w.bystander.pk, "display_name": "G2 Event attendee"}]}
        elif supervised:
            saved = SupervisedSession.objects.get(pk=response.data["id"])
            assert (saved.event_id, saved.machine_id, saved.instructor_id) == (w.event.pk, w.machine.pk, w.actor.pk)
        else:
            request = name == "public-machine-job-submit"
            subject = MachineServiceRequest.objects.get(pk=response.data["id"]) if request else MachineSession.objects.get(pk=response.data["id"])
            link = MachineEventLink.objects.get(**{"service_request" if request else "session": subject})
            assert (link.event_id, link.machine_type_id, link.source, link.makerspace_id) == (
                w.event.pk, w.kind.pk, "requester", w.space.pk)
            assert MachineEventLink.objects.filter(event=w.event).count() == 1

    def hidden(response):
        assert response.data == {"results": []}

    audit = () if picker else ("machine_session.supervised_opened",) if supervised else (
        ("machine_service.submitted", "machine_event.linked", "machine_service.file_attached") if
        name == "public-machine-job-submit" else ("machine_session.started", "machine_event.linked"))
    # 342: an explicit event while Events is off is 400 events_off; 517 additionally
    # forbids the subject INSERT even though the surrounding transaction rolls back.
    # 494/520: public requester membership, person discovery, and addressed session
    # standing keep their separate contracts.
    foreign = (403, "membership_required") if name == "public-machine-job-submit" else (
        (403, "permission_denied") if supervised and not picker else (404, "not_found"))
    prove(w, "events", lambda c: command(c, name, "get" if picker else "post", args, body), check,
          status=200 if picker else 201, audits=audit,
          off=(200, None) if picker else (404, "module_disabled") if supervised else (400, "events_off"),
          off_check=hidden if picker else None, foreign=foreign,
          foreign_off=(404, "module_disabled") if supervised and not picker else foreign)
