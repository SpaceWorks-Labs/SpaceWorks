"""Shared fixtures for the refund-case tests (local only)."""

from tests.payments.membership_rows import community_membership
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from apps.events.models import Event, EventRegistration
from apps.payments.models import MakerspacePaymentSettings, Payment, RefundPolicy
from tests.return_helpers import make_member, make_space


def space_with_currency(slug, currency="usd"):
    space = make_space(slug)
    settings = MakerspacePaymentSettings.for_makerspace(space)
    if settings.pk is None:
        settings.save()
    MakerspacePaymentSettings.objects.filter(pk=settings.pk).update(default_currency=currency)
    return space


def member(slug, space):
    user = make_member(slug, space, membership_role="member", role="requester")
    user.phone = "+919999999999"
    user.save(update_fields=["phone"])
    return user


def booking(space, user, *, starts_in=timedelta(days=2), amount="30.00"):
    """A confirmed booking whose charge was raised by the real workflow, then settled."""
    from apps.bookings import services_bookings
    from apps.bookings.models import BookableSpace
    room = BookableSpace.objects.create(makerspace=space, name=f"Room {BookableSpace.objects.count()}",
                                        approval_mode="instant", payment_amount=amount, is_public=True)
    start = timezone.now() + starts_in
    row = services_bookings.create_booking(room, starts_at=start, ends_at=start + timedelta(hours=1), member=user)
    payment = Payment.objects.get(subject_type=Payment.SubjectType.BOOKING, subject_id=row.pk)
    Payment.objects.filter(pk=payment.pk).update(status=Payment.Status.PAID_OFFLINE)
    payment.refresh_from_db()
    return row, payment


def deposit(space, user, *, status=Payment.Status.PAID_OFFLINE):
    from tests.return_helpers import make_accepted_request, make_product
    request = make_accepted_request(space, make_product(space), 1)
    return charge(space, request.requester, subject_type=Payment.SubjectType.LOAN_DEPOSIT, subject_id=request.pk,
                  status=status, amount="10.00")


def membership_charge(space, user, *, status=Payment.Status.PAID_OFFLINE):
    from apps.makerspaces.models import MakerspaceMembership
    membership = community_membership(space, user)
    return charge(space, user, subject_type=Payment.SubjectType.MAKERSPACE_MEMBERSHIP, subject_id=membership.pk,
                  status=status)


def finance_reader(space, slug="finance"):
    """VIEW_FINANCE without any subject action: only an organization grant can say that."""
    from apps.accounts import rbac
    from tests.account_split_g2_helpers import grant_organization_action
    from tests.return_helpers import make_user
    user = make_user(f"{space.slug}-{slug}", access_status="active")
    grant_organization_action(space, user, rbac.Action.VIEW_FINANCE)
    return user


def paid_event(space, *, starts_in=timedelta(days=2), amount="20.00"):
    start = timezone.now() + starts_in
    return Event.objects.create(
        makerspace=space, title="Paid workshop", starts_at=start, ends_at=start + timedelta(hours=2),
        is_public=True, status=Event.Status.PUBLISHED, payment_amount=amount,
    )


def registration(event, user, status=EventRegistration.Status.REGISTERED):
    return EventRegistration.objects.create(event=event, member=user, name="Attendee", email=user.email,
                                            phone="+919999999999", status=status)


def charge(space, user, *, subject_type=Payment.SubjectType.EVENT_REGISTRATION, subject_id=1,
           status=Payment.Status.PAID_OFFLINE, amount="20.00", currency="usd", **extra):
    return Payment.objects.create(
        makerspace=space, member=user, created_by=user, subject_type=subject_type, subject_id=subject_id,
        amount=Decimal(amount), currency=currency, status=status, subject_label="Paid workshop", **extra,
    )


def policy(space, area="events", *, full=48 * 60, partial=24 * 60, percent=50, fee="0.00"):
    return RefundPolicy.objects.create(makerspace=space, area=area, full_before_minutes=full,
                                       partial_before_minutes=partial, partial_percent=percent,
                                       cancellation_fee=Decimal(fee))


def receipt(**overrides):
    return {"method": "cash", "reference": "slip-1", "refunded_at": timezone.now(), **overrides}


def receipt_payload(**overrides):
    return {"method": "cash", "reference": "slip-1", "refunded_at": timezone.now().isoformat(), **overrides}


def base(space):
    return f"/api/v1/admin/makerspace/{space.pk}"
