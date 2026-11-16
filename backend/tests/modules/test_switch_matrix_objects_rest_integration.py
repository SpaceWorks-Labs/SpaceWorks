"""CX11B: signed server reads have their own transport, retained data and exact gates."""
import pytest
from django.core.cache import cache

from tests.bookings.integration_read_helpers import PREFIX, principal, read_world, signed  # noqa: F401
from tests.bookings.test_integration_reads import assert_target_refusal
from tests.modules.test_switch_matrix_objects_rest_support import no_domain_writes, domain_rows, switch


def response_pair(response):
    return response.status_code, response.json().get("code")

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("key", ["bookings", "bookings.api_read"])
@pytest.mark.parametrize("target", ["resource", "reservations", "booking"])
def test_signed_object_read_off_is_inert_and_on_restores_the_same_private_subject(read_world, key, target):
    w = read_world
    suffix = {"resource": f"resources/{w.resource.pk}/", "reservations": f"resources/{w.resource.pk}/bookings/",
              "booking": f"bookings/{w.booking.pk}/"}[target]
    url = PREFIX + suffix
    response = signed(w.client, url)
    assert response_pair(response) == (200, None), response.content
    payload = response.json()
    foreign = principal(w.foreign)
    missing = PREFIX + {"resource": "resources/999999999/", "reservations": "resources/999999999/bookings/",
                        "booking": "bookings/999999999/"}[target]
    def refusal_probes():
        assert_target_refusal(signed(foreign, url), 404, "not_found")
        assert_target_refusal(signed(w.client, missing), 404, "not_found")
        assert_target_refusal(signed(w.client, url, signature="0" * 64), 401, None)
    refusal_probes()
    before = domain_rows()
    original = switch(w.tenant, key)
    cache.clear()
    with no_domain_writes():
        response = signed(w.client, url)
    assert_target_refusal(response, 404, "not_found", authenticated=True)
    refusal_probes()
    assert domain_rows() == before
    switch(w.tenant, key, original=original)
    assert domain_rows() == before
    response = signed(w.client, url)
    assert response_pair(response) == (200, None)
    assert response.json() == payload
    refusal_probes()
