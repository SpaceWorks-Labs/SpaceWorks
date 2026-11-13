"""Closed submission unions retain the public booking leak boundary."""
import pytest
from drf_spectacular.generators import SchemaGenerator
from tests.bookings.test_public_booking_leaks import SPACE_FIELDS, AVAILABILITY_FIELDS

pytestmark = pytest.mark.django_db


def test_openapi_public_booking_contract_is_leak_safe_and_complete():
    schema = SchemaGenerator().get_schema(request=None, public=True)
    components = schema['components']['schemas']
    space_schema = components['PublicBookableSpace']
    input_schema = components['PublicBookingInput']
    path = '/api/v1/public/{makerspace_slug}/spaces/{public_token}/book/'
    response_schema = schema['paths'][path]['post']['responses']['201']['content']['application/json']['schema']
    availability_schema = components['PublicSpaceAvailability']

    assert set(space_schema['properties']) == SPACE_FIELDS
    assert set(input_schema['properties']) == {
        'starts_at', 'ends_at', 'custom_answers', 'certification_override_reason',
        'event_id',  # decision 342: optional event context on a machine-time booking
    }
    assert set(input_schema['required']) == {'starts_at', 'ends_at'}
    assert all(
        field['writeOnly'] for field in input_schema['properties'].values()
    )
    assert len(response_schema['oneOf']) == 2
    decoy, actual = response_schema['oneOf']
    assert set(decoy['properties']) == {'status'}
    assert set(actual['properties']) == {'status', 'public_token', 'confirmation_available', 'amount_due', 'currency', 'pay_online'}
    assert actual['properties']['public_token'] == {'type': 'string', 'format': 'uuid'}
    assert actual['properties']['confirmation_available'] == {'type': 'boolean'}
    assert actual['properties']['pay_online'] == {'type': 'boolean'}
    for branch in (decoy, actual):
        assert branch['additionalProperties'] is False
        assert set(branch['required']) == set(branch['properties'])
        assert 'custom_answers' not in branch['properties']
    assert set(availability_schema['properties']) == AVAILABILITY_FIELDS
    for component_name in (
        'PublicBookableSpace',
        'PublicSpaceAvailability',
        'PublicAvailabilityInterval',
    ):
        assert 'custom_answers' not in components[component_name]['properties']

    paths = {
        '/api/v1/public/{makerspace_slug}/spaces/': ('get', {'200', '400', '404', '429'}),
        '/api/v1/public/{makerspace_slug}/spaces/{public_token}/availability/': (
            'get', {'200', '400', '404', '429'}
        ),
        '/api/v1/public/{makerspace_slug}/spaces/{public_token}/book/': (
            'post', {'201', '400', '401', '403', '404', '409', '429'}
        ),
    }
    for path, (method, codes) in paths.items():
        operation = schema['paths'][path][method]
        if method == 'post':
            assert operation.get('security')
        else:
            # Anonymous stays valid; the contract also advertises the optional client credentials.
            security = operation.get('security', [])
            assert {} in security or security == []
            assert all(set(item) <= {'ServerHMAC', 'BrowserClient', 'PublishableKey'} for item in security)
        assert codes <= set(operation['responses'])
        token_parameters = [
            parameter
            for parameter in operation.get('parameters', [])
            if parameter['name'] == 'public_token'
        ]
        if '{public_token}' in path:
            assert token_parameters[0]['schema']['format'] == 'uuid'
    conflict = schema['paths'][
        '/api/v1/public/{makerspace_slug}/spaces/{public_token}/book/'
    ]['post']['responses']['409']['content']['application/json']['schema']
    assert conflict['$ref'].endswith('/HardwareRequestError')
