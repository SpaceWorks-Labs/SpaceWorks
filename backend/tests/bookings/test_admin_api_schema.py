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

from tests.bookings.admin_api_helpers import tenant, space, booking, urls


def test_staff_urls_origin_registry_and_openapi():
    makerspace = tenant('booking-origin')
    target, row = space(makerspace), None
    row = booking(target)
    factory = APIRequestFactory()
    for _method, url, _data in urls(makerspace, target, row):
        match = resolve(url)
        request = factory.get(url)
        request.resolver_match = match
        view = match.func.view_class(**match.func.view_initkwargs)
        view.kwargs = match.kwargs
        assert origin_scope._target_makerspace_id(request, view) == makerspace.pk
    schema = SchemaGenerator().get_schema(request=None, public=True)
    expected = {
        '/api/v1/admin/makerspaces/{makerspace_id}/spaces/': {'get', 'post'},
        '/api/v1/admin/spaces/{id}/': {'get', 'patch'},
        '/api/v1/admin/spaces/{id}/deactivate/': {'post'},
        '/api/v1/admin/spaces/{id}/image/presign/': {'post'},
        '/api/v1/admin/spaces/{id}/image/finalize/': {'post'},
        '/api/v1/admin/spaces/{id}/image/': {'delete'},
        '/api/v1/admin/spaces/{id}/bookings/': {'get'},
        '/api/v1/admin/spaces/{id}/booking-rules/': {'get', 'patch'},
        '/api/v1/admin/bookings/{id}/approve/': {'post'},
        '/api/v1/admin/bookings/{id}/reject/': {'post'},
        '/api/v1/admin/bookings/{id}/cancel/': {'post'},
        '/api/v1/admin/bookings/{id}/complete/': {'post'},
        '/api/v1/admin/bookings/{id}/no-show/': {'post'},
    }
    assert all(methods <= schema['paths'][path].keys() for path, methods in expected.items())
    fields = schema['components']['schemas']['BookableSpaceAdmin']['properties']
    assert 'image_key' not in fields
    assert {'show_public_availability', 'show_public_booker_names'} <= fields.keys()
    expected_errors = {
        '/api/v1/admin/makerspaces/{makerspace_id}/spaces/': {
            'get': {'403', '404'},
            'post': {'400', '403', '404'},
        },
        '/api/v1/admin/spaces/{id}/': {
            'get': {'403', '404'},
            'patch': {'400', '403', '404', '409'},
        },
        '/api/v1/admin/spaces/{id}/deactivate/': {
            'post': {'400', '403', '404', '409'},
        },
        '/api/v1/admin/spaces/{id}/image/presign/': {
            'post': {'400', '403', '404', '503'},
        },
        '/api/v1/admin/spaces/{id}/image/finalize/': {
            'post': {'400', '403', '404', '503'},
        },
        '/api/v1/admin/spaces/{id}/image/': {
            'delete': {'400', '403', '404', '503'},
        },
        '/api/v1/admin/spaces/{id}/bookings/': {
            'get': {'400', '403', '404'},
        },
        '/api/v1/admin/spaces/{id}/booking-rules/': {
            'get': {'400', '403', '404'},
            'patch': {'400', '403', '404', '409'},
        },
        '/api/v1/admin/bookings/{id}/approve/': {
            'post': {'400', '403', '404', '409'},
        },
        '/api/v1/admin/bookings/{id}/reject/': {
            'post': {'400', '403', '404', '409'},
        },
        '/api/v1/admin/bookings/{id}/cancel/': {
            'post': {'400', '403', '404', '409'},
        },
        '/api/v1/admin/bookings/{id}/complete/': {
            'post': {'400', '403', '404', '409'},
        },
        '/api/v1/admin/bookings/{id}/no-show/': {
            'post': {'400', '403', '404', '409'},
        },
    }
    rules_path = '/api/v1/admin/spaces/{id}/booking-rules/'
    for path, methods in expected_errors.items():
        for method, codes in methods.items():
            responses = schema['paths'][path][method]['responses']
            assert codes <= responses.keys()
            for code in codes:
                error_schema = responses[code]['content']['application/json'][
                    'schema'
                ]
                if path == rules_path and code == '400':
                    # Booking-rule 400s are DRF field-error maps (and the
                    # module-disabled {"module": ...} map), documented as a
                    # loose validation-error object, not HardwareRequestError.
                    assert '$ref' not in error_schema
                    assert error_schema.get('type') == 'object'
                else:
                    assert error_schema['$ref'].endswith('/HardwareRequestError')
