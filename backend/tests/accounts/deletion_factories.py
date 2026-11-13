"""Real owned records for account-deletion predicate and discovery tests."""
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from django.utils import timezone

from apps.accounts.models import User
from apps.bookings.models import BookableSpace, Booking
from apps.events.models import Event, EventRegistration
from apps.hardware_requests.models import HardwareRequest, PublicToolLoan
from apps.machines.models import MachineServiceRequest, MachineType, ServiceQueue
from apps.makerspaces.models import Makerspace
from apps.payments.models import Payment


def identity():
    return User.objects.create_user(username=f"delete-{uuid4().hex}")


def space():
    slug = f"delete-{uuid4().hex}"
    return Makerspace.objects.create(name=slug, slug=slug)


def request(user, tenant, status="returned"):
    return HardwareRequest.objects.create(
        requester=user, makerspace=tenant, requester_username=user.username, status=status,
    )


def loan(user, tenant, status="returned"):
    return PublicToolLoan.objects.create(
        request=request(user, tenant), requester=user, makerspace=tenant,
        target_type="product", target_id=1, target_label="Tool", status=status,
    )


def payment(user, tenant, *, status="pending", subject_type="loan_late_fee", via=None):
    subject = request(user, tenant)
    row = Payment.objects.create(
        member=user, makerspace=tenant, via_makerspace=via,
        subject_type=subject_type, subject_id=subject.pk, amount=Decimal("10.00"),
        currency="usd", created_by=user,
    )
    if status != "pending":
        # Match ledger fixtures: pending -> terminal is a permitted one-way write.
        Payment.objects.filter(pk=row.pk).update(status=status)
        row.refresh_from_db()
    return row


def booking(user, tenant, *, status="confirmed", ends_at=None):
    ends_at = ends_at or timezone.now() + timedelta(days=1)
    resource = BookableSpace.objects.create(makerspace=tenant, name="Room")
    return Booking.objects.create(
        space=resource, member=user, name="Member", email="member@example.com",
        phone="123456789", starts_at=ends_at - timedelta(hours=1), ends_at=ends_at, status=status,
    )


def registration(user, tenant, *, status="registered", event_status="published", ends_at=None, **kwargs):
    ends_at = ends_at or timezone.now() + timedelta(days=1)
    event = Event.objects.create(
        makerspace=tenant, title="Workshop", starts_at=ends_at - timedelta(hours=1),
        ends_at=ends_at, status=event_status,
    )
    return EventRegistration.objects.create(
        event=event, member=user, name="Member", email="member@example.com",
        phone="123456789", status=status, **kwargs,
    )


def service_job(user, tenant, *, status="pending", legacy=False, requester=None):
    machine_type, _ = MachineType.objects.get_or_create(
        makerspace=tenant, slug="deletion-service", defaults={"name": "Service"},
    )
    queue, _ = ServiceQueue.objects.get_or_create(
        makerspace=tenant, name="Service", defaults={"machine_type": machine_type},
    )
    return MachineServiceRequest.objects.create(
        makerspace=tenant, queue=queue, member=None if legacy else user,
        requester=requester or user, title="Member job", status=status,
    )
