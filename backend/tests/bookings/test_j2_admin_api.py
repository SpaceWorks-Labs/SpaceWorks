from tests.account_split.sweep_g2_helpers import staff_user
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.bookings.models import BookableSpace, Booking
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from tests.handout_roles import grant_handout

pytestmark = pytest.mark.django_db


def client_for(actor):
    client = APIClient()
    client.force_authenticate(actor)
    return client


def user(username):
    return User.objects.create_user(
        username=username,
        access_status=User.AccessStatus.ACTIVE,
    )


def grant(actor, makerspace, role=MakerspaceMembership.Role.SPACE_MANAGER):
    slug = {"print_manager": "machine_manager", "custom": "member"}.get(role, role)
    assigned_role = makerspace.roles.get(slug=slug)
    return MakerspaceMembership.objects.create(
        user=actor, makerspace=makerspace,
        role=assigned_role.legacy_role or "custom", assigned_role=assigned_role,
    )


def booking(target, email, start):
    return Booking.objects.create(
        space=target,
        name='Ada',
        email=email,
        phone='123',
        starts_at=start,
        ends_at=start + timedelta(hours=1),
        status=Booking.Status.PENDING,
    )


def test_pending_booking_approve_reject_endpoints_are_scoped_and_typed():
    makerspace = Makerspace.objects.create(
        name='Booking approval API',
        slug='booking-approval-api',
    )
    actor = staff_user(makerspace, 'booking-approval-manager', staff_role="space_manager")

    target = BookableSpace.objects.create(
        makerspace=makerspace,
        name='Workshop',
        approval_mode=BookableSpace.ApprovalMode.APPROVE,
    )
    start = timezone.now() + timedelta(hours=1)
    approved = booking(target, 'ada@example.com', start)
    rejected = booking(target, 'grace@example.com', start)
    client = client_for(actor)

    response = client.post(
        reverse('admin-booking-approve', kwargs={'pk': approved.pk}),
        {},
        format='json',
    )
    assert response.status_code == 200
    assert response.data['status'] == Booking.Status.CONFIRMED

    conflict = client.post(
        reverse('admin-booking-approve', kwargs={'pk': rejected.pk}),
        {},
        format='json',
    )
    rejected.refresh_from_db()
    assert conflict.status_code == 409
    assert conflict.data['code'] == 'booking_conflict'
    assert rejected.status == Booking.Status.PENDING

    missing_reason = client.post(
        reverse('admin-booking-reject', kwargs={'pk': rejected.pk}),
        {},
        format='json',
    )
    assert missing_reason.status_code == 400
    rejected.refresh_from_db()
    assert rejected.status == Booking.Status.PENDING

    response = client.post(
        reverse('admin-booking-reject', kwargs={'pk': rejected.pk}),
        {'reason': 'Resource unavailable'},
        format='json',
    )
    assert response.status_code == 200
    assert response.data['status'] == Booking.Status.REJECTED
    repeated = client.post(
        reverse('admin-booking-reject', kwargs={'pk': rejected.pk}),
        {'reason': 'not accepted'},
        format='json',
    )
    assert repeated.status_code == 409
    assert repeated.data['code'] == 'invalid_transition'
    rejected.refresh_from_db()
    assert rejected.status == Booking.Status.REJECTED
    assert rejected.decision_reason == 'Resource unavailable'


def test_booking_approval_endpoint_returns_403_for_visible_non_manager():
    makerspace = Makerspace.objects.create(
        name='Booking approval denied',
        slug='booking-approval-denied',
    )
    actor = staff_user(makerspace, 'booking-approval-denied-user', staff_role="handover")

    target = BookableSpace.objects.create(
        makerspace=makerspace,
        name='Workshop',
    )
    row = booking(
        target,
        'ada@example.com',
        timezone.now() + timedelta(hours=1),
    )
    assert client_for(actor).post(
        reverse('admin-booking-approve', kwargs={'pk': row.pk}),
        {},
        format='json',
    ).status_code == 403
