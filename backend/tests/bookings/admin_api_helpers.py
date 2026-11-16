from datetime import timedelta

import pytest
from django.contrib import admin
from django.urls import resolve, reverse
from django.utils import timezone
from drf_spectacular.generators import SchemaGenerator
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient, APIRequestFactory

from apps.accounts import rbac
from apps.accounts.models import User
from apps.bookings import services, storage
from apps.bookings.models import BookableSpace, Booking
from apps.makerspaces import origin_scope
from apps.makerspaces import limits
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from tests.handout_roles import grant_handout

pytestmark = pytest.mark.django_db

def tenant(slug='booking-admin', **values):
    return Makerspace.objects.create(name=slug, slug=slug, **values)


def user(name, role=User.Role.REQUESTER, **values):
    values.setdefault('access_status', User.AccessStatus.ACTIVE)
    if values.pop('is_superuser', False):
        return User.objects.create_superuser(username=name, role=User.Role.SUPERADMIN, **values)
    return User.objects.create_user(username=name, role=role, **values)


def grant(actor, makerspace, role=MakerspaceMembership.Role.SPACE_MANAGER):
    slug = {"print_manager": "machine_manager", "custom": "member"}.get(role, role)
    assigned_role = makerspace.roles.get(slug=slug)
    # One account per person: any role but Member is a staff-track row (community rows hold only Member).
    manager = MakerspaceMembership.objects if slug == "member" else MakerspaceMembership.staff_tracks
    extra = {} if slug == "member" else {"track": MakerspaceMembership.Track.STAFF}
    return manager.create(
        user=actor, makerspace=makerspace,
        role=assigned_role.legacy_role or "custom", assigned_role=assigned_role, **extra,
    )


def space(makerspace, **values):
    defaults = {'name': 'Development Room', 'is_public': True}
    defaults.update(values)
    return BookableSpace.objects.create(makerspace=makerspace, **defaults)


def booking(bookable_space, **values):
    start = values.pop('starts_at', timezone.now() - timedelta(hours=2))
    defaults = {
        'name': 'Ada',
        'email': 'ada@example.com',
        'phone': '123',
        'starts_at': start,
        'ends_at': start + timedelta(hours=1),
    }
    defaults.update(values)
    return Booking.objects.create(space=bookable_space, **defaults)


def client_for(actor):
    client = APIClient()
    client.force_authenticate(actor)
    return client


def urls(makerspace, bookable_space, row):
    return [
        ('get', reverse('admin-bookable-space-list-create', kwargs={'makerspace_id': makerspace.pk}), None),
        ('post', reverse('admin-bookable-space-list-create', kwargs={'makerspace_id': makerspace.pk}), {'name': 'New'}),
        ('get', reverse('admin-bookable-space-detail', kwargs={'pk': bookable_space.pk}), None),
        ('patch', reverse('admin-bookable-space-detail', kwargs={'pk': bookable_space.pk}), {'name': 'Edit'}),
        ('post', reverse('admin-bookable-space-deactivate', kwargs={'pk': bookable_space.pk}), {}),
        ('post', reverse('admin-bookable-space-image-presign', kwargs={'pk': bookable_space.pk}), {'filename': 'x.png', 'content_type': 'image/png'}),
        ('post', reverse('admin-bookable-space-image-finalize', kwargs={'pk': bookable_space.pk}), {'object_key': 'x'}),
        ('delete', reverse('admin-bookable-space-image-delete', kwargs={'pk': bookable_space.pk}), None),
        ('get', reverse('admin-space-booking-list', kwargs={'pk': bookable_space.pk}), None),
        ('get', reverse('admin-bookable-space-booking-rules', kwargs={'pk': bookable_space.pk}), None),
        ('patch', reverse('admin-bookable-space-booking-rules', kwargs={'pk': bookable_space.pk}), {'booking_lead_time_minutes': 90}),
        ('post', reverse('admin-booking-approve', kwargs={'pk': row.pk}), {}),
        ('post', reverse('admin-booking-reject', kwargs={'pk': row.pk}), {}),
        ('post', reverse('admin-booking-cancel', kwargs={'pk': row.pk}), {}),
        ('post', reverse('admin-booking-complete', kwargs={'pk': row.pk}), {}),
        ('post', reverse('admin-booking-no-show', kwargs={'pk': row.pk}), {}),
    ]


def call(client, method, url, data):
    return getattr(client, method)(url, data=data, format='json')


