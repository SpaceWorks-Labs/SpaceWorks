"""Real owned source rows and real signed-upload/email-code grants for reporting."""
from datetime import timedelta

from django.utils import timezone

from apps.bookings.models import Booking
from apps.machines.models import MachineServiceRequest, MachineSession, ServiceQueue
from tests.maintenance.l16_helpers import loan, world
from tests.maintenance.route_support_cx11b_g3 import isolation, person_client

SOURCES = {"loan": ("inventory", "inventory.issue_reporting", "loans.enabled"),
           "booking": ("rooms", "bookings.issue_reporting", "bookings"),
           "job": ("machines", "machines.issue_reporting", "machines"),
           "session": ("machines", "machines.issue_reporting", "machines.sessions")}


def report_world(source, native):
    w = world("g3-report")
    area, _, _ = SOURCES[source]
    isolation(w, area, "reporting")
    request, w.person = loan(w)
    w.origin, w.origin_field, w.subject, w.kind = request, "loan", w.product, "inventory_product"
    w.link = {"loan_id": request.pk}
    if source == "booking":
        w.origin = Booking.objects.create(space=w.room, member=w.person, starts_at=timezone.now(),
            ends_at=timezone.now() + timedelta(hours=1), status="confirmed", name="Retained booker", email=w.person.email)
        w.link, w.origin_field, w.subject, w.kind = {"booking_id": w.origin.pk}, "booking", w.room, "bookable_space"
    elif source == "job":
        queue = ServiceQueue.objects.create(makerspace=w.space, machine_type=w.machine.machine_type,
                                            name="Retained reporting queue")
        w.origin = MachineServiceRequest.objects.create(queue=queue, makerspace=w.space, member=w.person, requester=w.person,
            assigned_machine=w.machine, title="Retained completed job", status="completed")
        w.link, w.origin_field, w.subject, w.kind = {"machine_job_id": w.origin.pk}, "machine_job", w.machine, "machine"
    elif source == "session":
        w.space.enabled_features = sorted(set(w.space.enabled_features) | {"machines.sessions"})
        w.space.save(update_fields=["enabled_features"])
        w.origin = MachineSession.objects.create(makerspace=w.space, machine=w.machine, machine_type=w.machine.machine_type,
            member=w.person, source="staff", started_at=timezone.now() - timedelta(minutes=10))
        w.link, w.origin_field, w.subject, w.kind = {"machine_session_id": w.origin.pk}, "machine_session", w.machine, "machine"
    w.client = person_client(w.person, w.space, native)
    w.body = {"makerspace_id": w.space.pk, **w.link, "title": "Loose handle", "description": "Handle wobbles"}
    return w


def otp(space, email, code="752903"):
    from apps.accounts.models import EmailVerificationChallenge
    from apps.accounts.services_registration import _digest
    from apps.hardware_requests.contact_verification import email_key
    from apps.makerspaces.anonymous_requesters import get_or_create_anonymous_requester
    return EmailVerificationChallenge.objects.create(user=get_or_create_anonymous_requester(space),
        email=email_key(space, email), code_digest=_digest(code), expires_at=timezone.now() + timedelta(minutes=10),
        last_sent_at=timezone.now())
