from tests.account_split.sweep_g2_helpers import staff_user
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


from tests.bookings.admin_api_helpers import (
    tenant, user, grant, space, booking, client_for, urls, call,
)


def test_manage_bookings_grant_delta_is_exact():
    makerspace = tenant()
    allowed = set()
    for role, _label in MakerspaceMembership.Role.choices:
        actor = staff_user(makerspace, f'booking-{role}', staff_role=role)

        if rbac.can(actor, rbac.Action.MANAGE_BOOKINGS, makerspace.pk):
            allowed.add(role)
    root = user('booking-root', role=User.Role.SUPERADMIN, is_superuser=True)
    assert allowed == {MakerspaceMembership.Role.SPACE_MANAGER, MakerspaceMembership.Role.BOOKING_MANAGER}
    assert rbac.can(root, rbac.Action.MANAGE_BOOKINGS, makerspace.pk)


def test_every_endpoint_enforces_active_staff_and_module():
    makerspace = tenant('booking-guards')
    bookable_space, row = space(makerspace), None
    row = booking(bookable_space)
    cases = (
        (APIClient(), 401),
        (client_for(user('booking-inactive', is_active=False)), 403),
        (
            client_for(
                user(
                    'booking-suspended',
                    access_status=User.AccessStatus.SUSPENDED,
                )
            ),
            403,
        ),
        (client_for(user('booking-outsider')), 404),
    )
    for client, expected_status in cases:
        assert all(
            call(client, method, url, data).status_code == expected_status
            for method, url, data in urls(makerspace, bookable_space, row)
        )
    manager = staff_user(makerspace, 'booking-module-manager', staff_role="space_manager")

    makerspace.enabled_modules.remove('bookings')
    makerspace.save(update_fields=['enabled_modules'])
    assert all(
        call(client_for(manager), method, url, data).status_code == 404  # #183B: typed 404 when the module is off
        for method, url, data in urls(makerspace, bookable_space, row)
    )


def test_invisible_object_scopes_return_404_before_permission():
    cross_target = tenant('booking-cross-target')
    cross_actor = staff_user(tenant('booking-cross-own'), 'booking-cross-manager', staff_role="space_manager")

    archived = tenant('booking-archived', archived_at=timezone.now())
    archived_actor = staff_user(archived, 'booking-archived-manager', staff_role="space_manager")

    for makerspace, actor in (
        (cross_target, cross_actor),
        (archived, archived_actor),
    ):
        target = space(makerspace)
        row = booking(target)
        assert all(
            call(client_for(actor), method, url, data).status_code == 404
            for method, url, data in urls(makerspace, target, row)
        )


@pytest.mark.parametrize(
    'role',
    [
        MakerspaceMembership.Role.INVENTORY_MANAGER,
        MakerspaceMembership.Role.PRINT_MANAGER,
    ],
)
def test_visible_underprivileged_roles_get_403(role):
    makerspace = tenant(f'booking-denied-{role}')
    actor = staff_user(makerspace, f'booking-denied-user-{role}', staff_role=role)

    target = space(makerspace)
    assert client_for(actor).get(
        reverse('admin-bookable-space-detail', kwargs={'pk': target.pk})
    ).status_code == 403


def test_visible_front_desk_role_gets_403():
    """Separate from the parametrized legacy roles because handover is a custom role now:
    there is no enum member to feed the parametrize list."""
    makerspace = tenant('booking-denied-front-desk')
    actor = staff_user(makerspace, 'booking-denied-user-front-desk', staff_role="handover")

    target = space(makerspace)
    assert client_for(actor).get(
        reverse('admin-bookable-space-detail', kwargs={'pk': target.pk})
    ).status_code == 403


def test_space_crud_allowlist_flags_and_validation():
    makerspace = tenant('booking-write')
    actor = staff_user(makerspace, 'booking-manager', staff_role='space_manager')

    client = client_for(actor)
    created = client.post(
        reverse('admin-bookable-space-list-create', kwargs={'makerspace_id': makerspace.pk}),
        {
            'name': 'Studio',
            'show_public_availability': True,
            'show_public_booker_names': True,
            'image_key': 'secret',
            'is_active': False,
        },
        format='json',
    )
    assert created.status_code == 201
    assert set(created.data) == {
        'clone_enabled', 'staff_tools_enabled', 'can_copy_booking_rules',
        'recurring_enabled', 'staff_grants_enabled', 'broadcasts_enabled',
        'staff_permissions', 'can_manage_grants', 'report_features',
        'passes_enabled', 'checkin_enabled', 'website_enabled', 'embed_enabled',
        'id', 'public_token', 'makerspace_id', 'name', 'kind', 'description',
        'capacity', 'location', 'image_url', 'is_public',
        'show_public_availability', 'show_public_booker_names', 'is_active',
        'approval_mode', 'custom_form', 'requester_notifications_enabled',
        'machine_type', 'machine', 'buffer_before_minutes', 'buffer_after_minutes', 'cancellation_cutoff_hours',
        'payment_amount',
        'min_booking_duration_minutes', 'max_booking_duration_minutes',
        'booking_lead_time_minutes', 'max_booking_advance_days',
        'effective_requester_notifications_enabled',
        'created_by_id', 'created_at', 'updated_at',
    }
    assert 'image_key' not in created.data and created.data['is_active'] is True
    invalid = client.patch(
        reverse('admin-bookable-space-detail', kwargs={'pk': created.data['id']}),
        {'show_public_availability': False},
        format='json',
    )
    assert invalid.status_code == 400
    assert invalid.data['code'] == 'booker_names_requires_availability'


def test_booking_control_admins_are_read_only():
    for model in (BookableSpace, Booking):
        model_admin = admin.site._registry[model]
        assert model_admin.has_add_permission(None) is False
        assert model_admin.has_change_permission(None) is False
        assert model_admin.has_delete_permission(None) is False
        assert set(model_admin.readonly_fields) == {
            field.name for field in model._meta.fields
        }


def test_duplicate_finalize_loser_preserves_winner_object_and_accounting(
    monkeypatch,
):
    makerspace = tenant(
        'booking-finalize-race',
        resource_limit_overrides={'storage': 1000},
    )
    actor = staff_user(makerspace, 'booking-finalize-race-manager', staff_role="space_manager")

    target = space(makerspace)
    object_key = (
        f'spaces/{makerspace.pk}/{target.pk}/images/concurrent.png'
    )
    staging_key = storage.staging_key(object_key)
    live_objects = {object_key, staging_key}
    original_set_space_image = services.set_space_image

    monkeypatch.setattr(limits, 'is_self_host', lambda: False)
    monkeypatch.setattr(
        storage,
        'finalize_upload',
        lambda key: storage.FinalizeResult('ok', 25),
    )
    monkeypatch.setattr(storage, 'sniff_is_valid_image', lambda key: True)
    monkeypatch.setattr(storage, 'delete_object', live_objects.discard)

    def winner_attaches_before_loser(*args, **kwargs):
        original_set_space_image(*args, **kwargs)
        raise ValidationError(
            {'object_key': 'This image was attached by another request.'}
        )

    monkeypatch.setattr(
        services,
        'set_space_image',
        winner_attaches_before_loser,
    )
    response = client_for(actor).post(
        reverse(
            'admin-bookable-space-image-finalize',
            kwargs={'pk': target.pk},
        ),
        {'object_key': object_key},
        format='json',
    )

    target.refresh_from_db()
    makerspace.refresh_from_db()
    assert response.status_code == 400
    assert target.image_key == object_key
    assert object_key in live_objects
    assert staging_key not in live_objects
    assert makerspace.storage_bytes_used == 25


def test_booking_list_is_space_scoped_and_lifecycle_is_typed():
    own, other = tenant('booking-own'), tenant('booking-other')
    actor = staff_user(own, 'booking-list-manager', staff_role="space_manager")

    own_space, other_space = space(own), space(other)
    own_row, secret = booking(own_space), booking(other_space, email='secret@example.com')
    client = client_for(actor)
    response = client.get(
        reverse('admin-space-booking-list', kwargs={'pk': own_space.pk})
    )
    assert [item['id'] for item in response.data['results']] == [own_row.pk]
    assert response.data['results'][0]['email'] == 'ada@example.com'
    assert secret.email not in str(response.data)
    cancelled = client.post(
        reverse('admin-booking-cancel', kwargs={'pk': own_row.pk}),
        {},
        format='json',
    )
    conflict = client.post(
        reverse('admin-booking-cancel', kwargs={'pk': own_row.pk}),
        {},
        format='json',
    )
    assert cancelled.data['status'] == Booking.Status.CANCELLED
    assert conflict.status_code == 409 and conflict.data['code'] == 'invalid_transition'


