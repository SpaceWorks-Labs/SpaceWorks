from tests.account_split.sweep_g2_helpers import staff_user
from datetime import timedelta

import pytest
from django.urls import resolve, reverse
from django.utils import timezone
from drf_spectacular.generators import SchemaGenerator
from rest_framework.test import APIClient, APIRequestFactory

from apps.accounts import rbac
from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.events import services
from apps.events.models import Event, EventRegistration
from apps.makerspaces import origin_scope
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from tests.handout_roles import grant_handout

pytestmark = pytest.mark.django_db
def make_space(slug='event-admin', **values):
    return Makerspace.objects.create(name=slug, slug=slug, **values)
def make_user(name, role=User.Role.REQUESTER, **values):
    values.setdefault('access_status', User.AccessStatus.ACTIVE)
    if values.pop('is_superuser', False):
        return User.objects.create_superuser(username=name, role=User.Role.SUPERADMIN, **values)
    return User.objects.create_user(username=name, role=role, **values)
def grant(user, space, role=MakerspaceMembership.Role.SPACE_MANAGER):
    slug = {"print_manager": "machine_manager", "custom": "member"}.get(role, role)
    assigned_role = space.roles.get(slug=slug)
    return MakerspaceMembership.objects.create(
        user=user, makerspace=space,
        role=assigned_role.legacy_role or "custom", assigned_role=assigned_role,
    )
def make_event(space, title='Workshop', status=Event.Status.DRAFT, **values):
    start = timezone.now() + timedelta(hours=1)
    defaults = {'starts_at': start, 'ends_at': start + timedelta(hours=1)}
    defaults.update(values)
    return Event.objects.create(
        makerspace=space, title=title, status=status, **defaults
    )
def make_registration(event, email='guest@example.com', **values):
    return EventRegistration.objects.create(
        event=event, name='Guest', email=email, phone='123', **values
    )
def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client
def event_payload(title='New event'):
    start = timezone.now() + timedelta(days=1)
    return {'title': title, 'starts_at': start.isoformat(),
            'ends_at': (start + timedelta(hours=2)).isoformat()}
def endpoint_calls(space, event, registration):
    return [
        ('get', reverse('admin-event-list-create', kwargs={'makerspace_id': space.pk}), None),
        ('post', reverse('admin-event-list-create', kwargs={'makerspace_id': space.pk}), event_payload()),
        ('get', reverse('admin-event-detail', kwargs={'pk': event.pk}), None),
        ('patch', reverse('admin-event-detail', kwargs={'pk': event.pk}), {'title': 'Changed'}),
        ('post', reverse('admin-event-publish', kwargs={'pk': event.pk}), {}),
        ('post', reverse('admin-event-cancel', kwargs={'pk': event.pk}), {}),
        ('post', reverse('admin-event-complete', kwargs={'pk': event.pk}), {}),
        ('get', reverse('admin-event-registration-list', kwargs={'pk': event.pk}), None),
        ('post', reverse('admin-event-registration-mark-attended', kwargs={'pk': registration.pk}), {}),
        ('post', reverse('admin-event-registration-approve', kwargs={'pk': registration.pk}), {}),
        ('post', reverse('admin-event-registration-reject', kwargs={'pk': registration.pk}), {}),
        ('post', reverse('admin-event-registration-promote', kwargs={'pk': registration.pk}), {}),
    ]
def call(client, method, url, data):
    return getattr(client, method)(url, data=data, format='json')
def test_manage_events_grant_delta_is_space_manager_plus_superadmin():
    space = make_space()
    roles = [role for role, _label in MakerspaceMembership.Role.choices]
    allowed = set()
    for role in roles:
        user = staff_user(space, f'role-{role}', staff_role=role)

        if rbac.can(user, rbac.Action.MANAGE_EVENTS, space.pk):
            allowed.add(role)
    superadmin = make_user('events-root', role=User.Role.SUPERADMIN, is_superuser=True)
    assert allowed == {MakerspaceMembership.Role.SPACE_MANAGER, MakerspaceMembership.Role.EVENT_MANAGER}
    assert rbac.can(superadmin, rbac.Action.MANAGE_EVENTS, space.pk)
def test_is_active_staff_rejects_invalid_actors_on_every_operation():
    space, event = make_space(), None
    event = make_event(space)
    registration = make_registration(event)
    actors = [
        None,
        make_user('inactive-events', is_active=False),
        make_user('suspended-events', access_status=User.AccessStatus.SUSPENDED),
        make_user('nonstaff-events'),
    ]
    for actor in actors:
        client = APIClient() if actor is None else client_for(actor)
        assert all(
            call(client, method, url, data).status_code in {401, 403, 404}
            for method, url, data in endpoint_calls(space, event, registration)
        )
def test_module_off_disables_every_operation():
    space = make_space()
    space.enabled_modules.remove('events')
    space.save(update_fields=['enabled_modules'])
    manager = staff_user(space, 'module-off-manager', staff_role="space_manager")

    event = make_event(space)
    registration = make_registration(event)
    assert all(
        call(client_for(manager), method, url, data).status_code == 404
        for method, url, data in endpoint_calls(space, event, registration)
    )
@pytest.mark.parametrize('superuser', [False, True])
def test_managers_and_visible_superadmins_succeed(superuser):
    space = make_space(f'event-success-{superuser}')
    actor = (make_user(f'event-actor-{superuser}', is_superuser=True) if superuser
             else staff_user(space, f'event-actor-{superuser}'))
    client = client_for(actor)
    created = client.post(
        reverse('admin-event-list-create', kwargs={'makerspace_id': space.pk}),
        event_payload(),
        format='json',
    )
    draft = Event.objects.get(pk=created.data['id'])
    published = make_event(space, 'Published', Event.Status.PUBLISHED)
    completed = make_event(space, 'Complete me', Event.Status.PUBLISHED)
    registration = make_registration(published)
    responses = [
        created,
        client.get(reverse('admin-event-list-create', kwargs={'makerspace_id': space.pk})),
        client.get(reverse('admin-event-detail', kwargs={'pk': draft.pk})),
        client.patch(reverse('admin-event-detail', kwargs={'pk': draft.pk}), {'title': 'Edit'}),
        client.post(reverse('admin-event-publish', kwargs={'pk': draft.pk}), {}, format='json'),
        client.get(reverse('admin-event-registration-list', kwargs={'pk': published.pk})),
        client.post(reverse('admin-event-registration-mark-attended', kwargs={'pk': registration.pk}), {}, format='json'),
        client.post(reverse('admin-event-cancel', kwargs={'pk': published.pk}), {}, format='json'),
        client.post(reverse('admin-event-complete', kwargs={'pk': completed.pk}), {}, format='json'),
    ]
    assert all(response.status_code < 300 for response in responses)
def test_visible_underprivileged_roles_get_403():
    for label in ("handover", "inventory_manager", "machine_manager"):
        space = make_space(f'event-denied-{label}')
        actor = staff_user(space, f'event-denied-user-{label}', staff_role=label)
        event = make_event(space)
        registration = make_registration(event)
        assert all(
            call(client_for(actor), method, url, data).status_code == 403
            for method, url, data in endpoint_calls(space, event, registration)
        )
def test_invisible_object_scopes_return_404_before_permission():
    spaces = [
        make_space('event-nonmember'),
        make_space('event-archived', archived_at=timezone.now()),
    ]
    actors = [
        make_user('event-outsider'),
        staff_user(spaces[1], 'event-archived-member'),
    ]
    for space, actor in zip(spaces, actors):
        event = make_event(space)
        registration = make_registration(event)
        for method, url, data in endpoint_calls(space, event, registration)[2:]:
            assert call(client_for(actor), method, url, data).status_code == 404
def test_lists_do_not_cross_tenants_or_leak_registration_pii():
    own, other = make_space('event-own'), make_space('event-other')
    manager = staff_user(own, 'event-list-manager', staff_role="space_manager")

    own_event, other_event = make_event(own, 'Own'), make_event(other, 'Other')
    make_registration(own_event, 'own@example.com')
    make_registration(other_event, 'secret@example.com')
    client = client_for(manager)
    events = client.get(reverse('admin-event-list-create', kwargs={'makerspace_id': own.pk}))
    registrations = client.get(reverse('admin-event-registration-list', kwargs={'pk': own_event.pk}))
    assert [row['id'] for row in events.data['results']] == [own_event.pk]
    assert [row['email'] for row in registrations.data['results']] == ['own@example.com']
    assert 'secret@example.com' not in str(events.data) + str(registrations.data)
def test_create_is_draft_and_patch_cannot_change_owned_fields():
    space, other = make_space('event-write'), make_space('event-write-other')
    actor = staff_user(space, 'event-write-manager', staff_role="space_manager")

    client = client_for(actor)
    created = client.post(
        reverse('admin-event-list-create', kwargs={'makerspace_id': space.pk}),
        event_payload(),
        format='json',
    )
    response = client.patch(
        reverse('admin-event-detail', kwargs={'pk': created.data['id']}),
        {'title': 'Allowed', 'status': 'completed', 'makerspace': other.pk, 'created_by': None},
        format='json',
    )
    event = Event.objects.get(pk=created.data['id'])
    assert created.status_code == 201 and created.data['status'] == Event.Status.DRAFT
    assert response.status_code == 200
    assert (event.status, event.makerspace_id, event.created_by_id) == (
        Event.Status.DRAFT, space.pk, actor.pk
    )
def test_lifecycle_errors_are_typed_and_service_failures_do_not_persist(monkeypatch):
    space = make_space('event-errors')
    actor = staff_user(space, 'event-error-manager', staff_role='space_manager')

    event = make_event(space)
    client = client_for(actor)
    url = reverse('admin-event-publish', kwargs={'pk': event.pk})
    assert client.post(url, {}, format='json').status_code == 200
    conflict = client.post(url, {}, format='json')
    before = event.title
    monkeypatch.setattr(services, 'update_event', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('failed')))
    client.raise_request_exception = False
    failed = client.patch(reverse('admin-event-detail', kwargs={'pk': event.pk}), {'title': 'No write'}, format='json')
    event.refresh_from_db()
    assert conflict.status_code == 409
    assert conflict.data == {'detail': 'Only draft events can be published.', 'code': 'invalid_transition'}
    assert failed.status_code == 500 and event.title == before
def test_fifo_pagination_and_attendance_response():
    space = make_space('event-fifo')
    actor = staff_user(space, 'event-fifo-manager', staff_role='space_manager')

    event = make_event(space, status=Event.Status.PUBLISHED)
    first = make_registration(event, 'first@example.com')
    second = make_registration(event, 'second@example.com')
    EventRegistration.objects.filter(pk=first.pk).update(created_at=timezone.now() - timedelta(hours=1))
    client = client_for(actor)
    url = reverse('admin-event-registration-list', kwargs={'pk': event.pk})
    page = client.get(f'{url}?page_size=1')
    attended = client.post(
        reverse('admin-event-registration-mark-attended', kwargs={'pk': first.pk}), {}, format='json'
    )
    assert page.data['results'][0]['id'] == first.pk and page.data['next']
    assert attended.status_code == 200 and attended.data['status'] == EventRegistration.Status.ATTENDED
    assert second.status == EventRegistration.Status.REGISTERED
def test_all_mutations_emit_audit_rows():
    space = make_space('event-audit')
    actor = staff_user(space, 'event-audit-manager', staff_role='space_manager')

    client = client_for(actor)
    created = client.post(reverse('admin-event-list-create', kwargs={'makerspace_id': space.pk}), event_payload(), format='json')
    event_id = created.data['id']
    client.patch(reverse('admin-event-detail', kwargs={'pk': event_id}), {'title': 'Updated'}, format='json')
    client.post(reverse('admin-event-publish', kwargs={'pk': event_id}), {}, format='json')
    registration = make_registration(Event.objects.get(pk=event_id))
    client.post(reverse('admin-event-registration-mark-attended', kwargs={'pk': registration.pk}), {}, format='json')
    client.post(reverse('admin-event-cancel', kwargs={'pk': event_id}), {}, format='json')
    complete = make_event(space, 'Complete audit', Event.Status.PUBLISHED)
    client.post(reverse('admin-event-complete', kwargs={'pk': complete.pk}), {}, format='json')
    assert set(AuditLog.objects.values_list('action', flat=True)) >= {
        'event.created', 'event.updated', 'event.published', 'event.cancelled',
        'event.completed', 'event.registration_attended',
    }
def test_staff_urls_reverse_and_origin_registry_resolves_owner():
    space = make_space('event-origin')
    event = make_event(space)
    registration = make_registration(event)
    urls = [url for _method, url, _data in endpoint_calls(space, event, registration)]
    assert len(set(urls)) == 10
    factory = APIRequestFactory()
    for url in urls:
        match = resolve(url)
        request = factory.get(url)
        request.resolver_match = match
        view = match.func.view_class(**match.func.view_initkwargs)
        view.kwargs = match.kwargs
        assert origin_scope._target_makerspace_id(request, view) == space.pk
    for public_name in ('public-event-list', 'public-event-register'):
        assert public_name not in origin_scope._MAKERSPACE_KWARG_ROUTES
        assert public_name not in origin_scope._MODEL_LOOKUPS
def test_openapi_contains_nine_operations_and_typed_components():
    schema = SchemaGenerator().get_schema(request=None, public=True)
    paths = {
        '/api/v1/admin/makerspaces/{makerspace_id}/events/': {'get', 'post'},
        '/api/v1/admin/events/{id}/': {'get', 'patch'},
        '/api/v1/admin/events/{id}/publish/': {'post'},
        '/api/v1/admin/events/{id}/cancel/': {'post'},
        '/api/v1/admin/events/{id}/complete/': {'post'},
        '/api/v1/admin/events/{id}/registrations/': {'get'},
        '/api/v1/admin/event-registrations/{id}/mark-attended/': {'post'},
        '/api/v1/admin/event-registrations/{id}/approve/': {'post'},
        '/api/v1/admin/event-registrations/{id}/reject/': {'post'},
        '/api/v1/admin/event-registrations/{id}/promote/': {'post'},
    }
    assert sum(len(methods) for methods in paths.values()) == 12
    assert all(methods <= schema['paths'][path].keys() for path, methods in paths.items())
    components = schema['components']['schemas']
    # Creation has organizer/partner fields; the write serializer is PATCH-only.
    assert {'EventCreate', 'PatchedEventWrite', 'EventAdmin', 'EventRegistrationAdmin'} <= components.keys()
    create_schema = schema['paths'][
        '/api/v1/admin/makerspaces/{makerspace_id}/events/'
    ]['post']['requestBody']['content']['application/json']['schema']
    patch_schema = schema['paths']['/api/v1/admin/events/{id}/']['patch'][
        'requestBody'
    ]['content']['application/json']['schema']
    assert create_schema == {'$ref': '#/components/schemas/EventCreate'}
    assert patch_schema == {'$ref': '#/components/schemas/PatchedEventWrite'}
    assert set(components['HardwareRequestError']['properties']) == {'detail', 'code'}
    validation_error_schema = {'type': 'object', 'additionalProperties': {}}
    assert schema['paths'][
        '/api/v1/admin/makerspaces/{makerspace_id}/events/'
    ]['post']['responses']['400']['content']['application/json']['schema'] == (
        validation_error_schema
    )
    for path, method in (
        ('/api/v1/admin/events/{id}/', 'patch'),
        ('/api/v1/admin/events/{id}/publish/', 'post'),
    ):
        assert schema['paths'][path][method]['responses']['400']['content'][
            'application/json'
        ]['schema'] == validation_error_schema
