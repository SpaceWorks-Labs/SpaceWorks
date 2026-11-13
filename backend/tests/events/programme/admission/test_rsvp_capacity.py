from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from django.db import close_old_connections
from apps.events.models import EventRegistration
from apps.events.hackathons.admission_errors import ProgrammeError
from apps.events.hackathons.admission_rsvp import rsvp
from tests.events.programme.admission.test_support import world, submitted, cmd

pytestmark = pytest.mark.django_db(transaction=True)


def test_overbooked_offers_never_exceed_the_hard_seat_ceiling(world):
    first, second = submitted(world), submitted(world, world.other)
    rsvp(event_id=world.event.pk, actor=world.owner, data=cmd(first.version, decision="accept"))
    with pytest.raises(ProgrammeError) as exc:
        rsvp(event_id=world.event.pk, actor=world.other, data=cmd(second.version, decision="accept"))
    assert exc.value.detail["code"] == "capacity_full"
    second.refresh_from_db()
    assert second.state == "offered" and second.rsvp_accepted_at is None
    assert EventRegistration.objects.filter(event=world.event, status="registered").count() == 1
    rsvp(event_id=world.event.pk, actor=world.other, data=cmd(second.version, decision="waitlist"))
    second.refresh_from_db()
    assert second.state == "waitlisted"


def test_two_simultaneous_rsvps_for_last_seat(world):
    first, second = submitted(world), submitted(world, world.other)
    barrier = Barrier(2)
    def respond(actor, app):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            try:
                rsvp(event_id=world.event.pk, actor=actor, data=cmd(app.version, decision="accept"))
                return "confirmed"
            except ProgrammeError as exc:
                return exc.detail["code"]
        finally:
            close_old_connections()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(respond, world.owner, first), pool.submit(respond, world.other, second)]
        outcomes = sorted(f.result(timeout=20) for f in futures)
    assert outcomes == ["capacity_full", "confirmed"]
    assert EventRegistration.objects.filter(event=world.event, status="registered").count() == 1
